"""Right-to-erasure: remove a node and purge it from Git history.

Mechanism (documented limits — see ADR 0006):
- the node is deleted from its part file, references to it are nulled,
  raw turns it came from are deleted, the derived .rag index is dropped;
- Git history is squashed to a single redacted baseline commit, reflogs are
  expired and objects pruned, so the old content is unrecoverable IN THIS
  STORE. Copies already exported or cloned elsewhere are out of reach.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from cortical_transfer.integrity import load_pack, save_pack
from cortical_transfer.schema import MemPack
from cortical_transfer.store import _AUTHOR, open_profile


def remove_node(pack: MemPack, node_id: str) -> list[str]:
    """Remove node from the pack, null dangling references. Returns its source_refs.

    Raises KeyError if the id does not exist."""
    target = next((n for n in pack.all_nodes() if n.id == node_id), None)
    if target is None:
        raise KeyError(node_id)
    for part in (pack.identity, pack.episodes, pack.threads):
        part[:] = [n for n in part if n.id != node_id]
    for n in pack.all_nodes():
        if n.superseded_by == node_id:
            n.superseded_by = None
        if n.parent_id == node_id:
            n.parent_id = None
    return target.source_refs


def _purge_raw(pack_dir: Path, turn_ids: list[str]) -> None:
    """Delete raw turns the redacted node was extracted from."""
    raw = pack_dir / "raw"
    if not raw.is_dir() or not turn_ids:
        return
    wanted = set(turn_ids)
    for f in raw.glob("*.jsonl"):
        lines = f.read_text(encoding="utf-8").splitlines()
        kept = []
        for line in lines:
            try:
                if json.loads(line).get("turn_id") in wanted:
                    continue
            except ValueError:
                pass
            kept.append(line)
        if len(kept) != len(lines):
            f.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


def redact(profile: str, node_id: str) -> str:
    """Erase a node from memory AND history. Returns the new baseline commit sha."""
    repo = open_profile(profile)
    pack_dir = Path(repo.working_dir)
    pack = load_pack(pack_dir)
    refs = remove_node(pack, node_id)
    _purge_raw(pack_dir, refs)
    shutil.rmtree(pack_dir / ".rag", ignore_errors=True)  # derived index may hold the text
    save_pack(pack, pack_dir)

    # squash: new orphan branch becomes the only history, old objects pruned
    repo.git.checkout("--orphan", "_redacting")
    repo.git.add(A=True)
    sha = repo.index.commit(
        f"chore: redact node {node_id} (history squashed for erasure)",
        author=_AUTHOR,
        committer=_AUTHOR,
    ).hexsha
    repo.git.branch("-D", "main")
    repo.git.branch("-m", "main")
    repo.git.reflog("expire", "--expire=now", "--all")
    repo.git.gc("--aggressive", "--prune=now")
    return sha
