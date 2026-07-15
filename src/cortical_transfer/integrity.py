"""MemPack directory I/O + SHA-256 integrity manifest (SPEC.md §5)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter

from cortical_transfer.schema import Manifest, MemPack, SemanticNode, now

_NODES = TypeAdapter(list[SemanticNode])
# JSON files hashed into the manifest; mempack.json itself is excluded (it holds the hashes).
_PARTS = ("identity.json", "episodes.json", "threads.json", "style.md")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump_nodes(nodes: list[SemanticNode]) -> bytes:
    return _NODES.dump_json(nodes, indent=2)


def save_pack(pack: MemPack, path: Path) -> None:
    """Write pack to `path` and record content hashes in the manifest."""
    path.mkdir(parents=True, exist_ok=True)
    files = {
        "identity.json": _dump_nodes(pack.identity),
        "episodes.json": _dump_nodes(pack.episodes),
        "threads.json": _dump_nodes(pack.threads),
        "style.md": pack.style.encode(),
    }
    pack.manifest.updated_at = now()
    pack.manifest.content_hashes = {name: _sha256(data) for name, data in files.items()}
    raw = path / "raw"
    if raw.is_dir():
        for f in sorted(raw.rglob("*")):
            if f.is_file():
                rel = f.relative_to(path).as_posix()
                pack.manifest.content_hashes[rel] = _sha256(f.read_bytes())
    for name, data in files.items():
        (path / name).write_bytes(data)
    (path / "mempack.json").write_bytes(pack.manifest.model_dump_json(indent=2).encode())


def load_pack(path: Path, verify: bool = True) -> MemPack:
    """Load pack from `path`; raises IntegrityError on hash mismatch unless verify=False."""
    manifest = Manifest.model_validate_json((path / "mempack.json").read_bytes())
    if verify:
        errors = verify_pack(path)
        if errors:
            raise IntegrityError("; ".join(errors))
    return MemPack(
        manifest=manifest,
        identity=_NODES.validate_json((path / "identity.json").read_bytes()),
        episodes=_NODES.validate_json((path / "episodes.json").read_bytes()),
        threads=_NODES.validate_json((path / "threads.json").read_bytes()),
        style=(path / "style.md").read_text(encoding="utf-8"),
    )


def verify_pack(path: Path) -> list[str]:
    """Return a list of integrity errors (empty = pack verifies)."""
    try:
        manifest = Manifest.model_validate_json((path / "mempack.json").read_bytes())
    except (OSError, ValueError) as e:
        return [f"mempack.json unreadable: {e}"]
    errors = []
    for name, expected in manifest.content_hashes.items():
        f = path / name
        if not f.is_file():
            errors.append(f"{name}: missing")
        elif _sha256(f.read_bytes()) != expected:
            errors.append(f"{name}: hash mismatch")
    for name in _PARTS:
        if name not in manifest.content_hashes:
            errors.append(f"{name}: not in manifest")
    return errors


class IntegrityError(Exception):
    pass


def _json_roundtrip_check() -> None:  # pragma: no cover
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = MemPack(identity=[SemanticNode(text="likes espresso")])
        save_pack(p, Path(d))
        q = load_pack(Path(d))
        assert json.loads(p.model_dump_json()) == json.loads(q.model_dump_json())


if __name__ == "__main__":  # pragma: no cover
    _json_roundtrip_check()
    print("ok")
