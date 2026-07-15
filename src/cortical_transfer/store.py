"""Git-backed memory store: one profile = one Git repo whose worktree is the MemPack."""

from __future__ import annotations

import os
from pathlib import Path

from git import Actor, Repo
from pydantic import TypeAdapter

from cortical_transfer.integrity import save_pack
from cortical_transfer.schema import MemPack, SemanticNode

_NODES = TypeAdapter(list[SemanticNode])
_PARTS = ("identity.json", "episodes.json", "threads.json")
_AUTHOR = Actor("cortical-transfer", "ct@localhost")


def root_dir() -> Path:
    return Path(os.environ.get("CT_HOME", str(Path.home() / ".cortical-transfer")))


def profile_path(profile: str = "default") -> Path:
    return root_dir() / profile


def init_profile(profile: str = "default") -> Path:
    path = profile_path(profile)
    if (path / ".git").exists():
        raise FileExistsError(f"profile '{profile}' already exists at {path}")
    path.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(path, initial_branch="main")
    save_pack(MemPack(), path)
    _commit(repo, "chore: initialize empty memory profile")
    return path


def open_profile(profile: str = "default") -> Repo:
    path = profile_path(profile)
    if not (path / ".git").exists():
        raise FileNotFoundError(f"no profile '{profile}' — run `ct init` first")
    return Repo(path)


def commit_pack(pack: MemPack, profile: str, message: str) -> str:
    """Save pack into the profile worktree and commit. Returns commit hexsha."""
    repo = open_profile(profile)
    save_pack(pack, Path(repo.working_dir))
    return _commit(repo, message)


def _commit(repo: Repo, message: str) -> str:
    repo.git.add(A=True)
    return repo.index.commit(message, author=_AUTHOR, committer=_AUTHOR).hexsha


def log(profile: str = "default") -> list[tuple[str, str, str]]:
    """[(short_sha, iso_date, message summary)] newest first."""
    return [
        (c.hexsha[:8], c.committed_datetime.isoformat(), str(c.summary))
        for c in open_profile(profile).iter_commits()
    ]


def _nodes_at(repo: Repo, rev: str, part: str) -> dict[str, SemanticNode]:
    try:
        raw = repo.git.show(f"{rev}:{part}")
    except Exception:
        return {}
    return {n.id: n for n in _NODES.validate_json(raw)}


def diff(profile: str, rev_a: str, rev_b: str = "HEAD") -> list[str]:
    """Human-readable memory changes rev_a -> rev_b."""
    repo = open_profile(profile)
    lines: list[str] = []
    for part in _PARTS:
        a, b = _nodes_at(repo, rev_a, part), _nodes_at(repo, rev_b, part)
        section = part.removesuffix(".json")
        for nid in b.keys() - a.keys():
            lines.append(f"+ [{section}] {b[nid].text}")
        for nid in a.keys() - b.keys():
            lines.append(f"- [{section}] {a[nid].text}")
        for nid in a.keys() & b.keys():
            old, new = a[nid], b[nid]
            if old.text != new.text:
                lines.append(f"~ [{section}] {old.text!r} -> {new.text!r}")
            elif old.superseded_by != new.superseded_by:
                lines.append(f"~ [{section}] superseded: {old.text}")
    if _show(repo, rev_a, "style.md") != _show(repo, rev_b, "style.md"):
        lines.append("~ [style] style card changed")
    return lines


def _show(repo: Repo, rev: str, path: str) -> str | None:
    try:
        return str(repo.git.show(f"{rev}:{path}"))
    except Exception:
        return None


def checkout(profile: str, rev: str) -> str:
    """Restore the memory state of `rev` as a NEW commit (history is never lost)."""
    repo = open_profile(profile)
    repo.git.checkout(rev, "--", ".")
    return _commit(repo, f"revert: restore memory state from {rev}")
