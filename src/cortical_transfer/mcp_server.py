"""MCP server: the local memory profile, live, for any MCP client (Claude Code, OpenCode, ...).

Run with `ct-mcp` (stdio transport). Profile via CT_PROFILE, default "default".
Requires the [mcp] extra: pip install "cortical-transfer[mcp]".

Register in Claude Code:  claude mcp add cortical-transfer -- ct-mcp
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from cortical_transfer import store
from cortical_transfer.inject import build_context
from cortical_transfer.integrity import load_pack
from cortical_transfer.sanitize import sanitize_text
from cortical_transfer.schema import MemPack, SemanticNode

mcp = FastMCP("cortical-transfer")


def _profile() -> str:
    return os.environ.get("CT_PROFILE", "default")


def _pack() -> MemPack:
    return load_pack(store.profile_path(_profile()))


@mcp.tool()
def memory_profile(budget_tokens: int = 2000, query: str = "") -> str:
    """The user's portable memory as a ready-to-inject context block.

    Call once at session start and put the block in your context: it contains
    who the user is, open threads, notable history and interaction style.
    Optional `query` ranks facts relevant to the session topic first."""
    return build_context(_pack(), budget_tokens, query or None)


@mcp.tool()
def memory_search(query: str) -> list[str]:
    """Case-insensitive substring search over live memory facts and tags."""
    # ponytail: substring over a few hundred nodes; route through embeddings
    # only if packs ever outgrow the context window (ADR 0005).
    q = query.lower()
    return [
        sanitize_text(n.text)  # MCP output enters an agent's prompt: a boundary (ADR 0004)
        for n in _pack().all_nodes()
        if not n.superseded_by and (q in n.text.lower() or any(q in t.lower() for t in n.tags))
    ]


@mcp.tool()
def memory_add_fact(text: str, part: str = "episodes", tags: list[str] | None = None) -> str:
    """Store one new fact about the user. `part`: identity | episodes | threads.

    Use when the user states something durable (identity), recounts something
    notable (episodes), or starts/continues ongoing work (threads)."""
    if part not in ("identity", "episodes", "threads"):
        raise ValueError("part must be identity, episodes or threads")
    pack = _pack()
    node = SemanticNode(text=sanitize_text(text), tags=tags or [])
    getattr(pack, part).append(node)
    store.commit_pack(pack, _profile(), f"feat: add fact via MCP ({part})")
    return node.id


def main() -> None:
    mcp.run()  # stdio


if __name__ == "__main__":
    main()
