import json
from pathlib import Path

import pytest

from cortical_transfer.integrity import IntegrityError, load_pack, save_pack, verify_pack
from cortical_transfer.schema import MemPack, SemanticNode, new_ulid


def make_pack() -> MemPack:
    return MemPack(
        identity=[SemanticNode(text="works on AI agents", granularity="summary", salience=0.9)],
        episodes=[SemanticNode(text="chose uv over pip", tags=["tooling"])],
        threads=[SemanticNode(text="app name still undecided")],
        style="Concise, Italian, informal.",
    )


def test_ulid_format() -> None:
    a, b = new_ulid(), new_ulid()
    assert len(a) == 26 and a != b
    assert all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in a)


def test_roundtrip_identical(tmp_path: Path) -> None:
    pack = make_pack()
    save_pack(pack, tmp_path)
    loaded = load_pack(tmp_path)
    assert json.loads(pack.model_dump_json()) == json.loads(loaded.model_dump_json())
    # and the on-disk JSON reparses to the same model
    save_pack(loaded, tmp_path)
    assert json.loads(load_pack(tmp_path).model_dump_json()) == json.loads(
        loaded.model_dump_json()
    )


def test_verify_clean(tmp_path: Path) -> None:
    save_pack(make_pack(), tmp_path)
    assert verify_pack(tmp_path) == []


def test_tamper_detected(tmp_path: Path) -> None:
    save_pack(make_pack(), tmp_path)
    f = tmp_path / "identity.json"
    f.write_text(f.read_text().replace("agents", "AGENTS"))
    errors = verify_pack(tmp_path)
    assert any("identity.json" in e for e in errors)
    with pytest.raises(IntegrityError):
        load_pack(tmp_path)
    # explicit override still loads
    assert load_pack(tmp_path, verify=False).identity[0].text


def test_missing_file_detected(tmp_path: Path) -> None:
    save_pack(make_pack(), tmp_path)
    (tmp_path / "style.md").unlink()
    assert any("style.md" in e for e in verify_pack(tmp_path))


def test_raw_files_hashed(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "conv-001.jsonl").write_text('{"role":"user","content":"hi"}\n')
    save_pack(make_pack(), tmp_path)
    assert verify_pack(tmp_path) == []
    (raw / "conv-001.jsonl").write_text("tampered")
    assert any("raw/conv-001.jsonl" in e for e in verify_pack(tmp_path))


def test_salience_bounds() -> None:
    with pytest.raises(ValueError):
        SemanticNode(text="x", salience=1.5)
