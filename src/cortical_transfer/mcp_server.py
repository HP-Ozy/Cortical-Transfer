"""MCP server (stdio) exposing the memory profile to any MCP client.

Profile comes from CT_PROFILE (default "default"). Run with `ct mcp serve`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from cortical_transfer import store
from cortical_transfer.inject import build_context
from cortical_transfer.integrity import load_pack
from cortical_transfer.sanitize import sanitize_text
from cortical_transfer.schema import Granularity, MemPack, SemanticNode

mcp = FastMCP("cortical-transfer")


def _profile() -> str:
    return os.environ.get("CT_PROFILE", "default")


def _pack() -> MemPack:
    return load_pack(store.profile_path(_profile()))


@mcp.tool()
def memory_get_context(query: str | None = None, budget: int = 2000) -> str:
    """Get the user's portable memory as a token-budgeted context block."""
    path = store.profile_path(_profile())
    return build_context(load_pack(path), budget_tokens=budget, query=query, pack_path=path)


@mcp.tool()
def memory_search(query: str) -> str:
    """Search memory nodes (case-insensitive substring over text and tags)."""
    q = query.lower()
    hits = [
        {"id": n.id, "part": part, "text": n.text, "salience": n.salience}
        for part, nodes in _parts().items()
        for n in nodes
        if q in n.text.lower() or any(q in t.lower() for t in n.tags)
    ]
    return json.dumps(hits, indent=2)


@mcp.tool()
def memory_add_fact(text: str, granularity: Granularity = "episode") -> str:
    """Add a fact to the user's memory. Returns the new node id."""
    pack = _pack()
    node = SemanticNode(text=sanitize_text(text), granularity=granularity, salience=0.7)
    (pack.identity if granularity == "summary" else pack.episodes).append(node)
    store.commit_pack(pack, _profile(), f"feat: add fact via MCP ({node.id})")
    return node.id


@mcp.tool()
def memory_export(path: str) -> str:
    """Export the memory as a portable .mempack file at `path`."""
    return str(store.export_pack(_profile(), Path(path)))


@mcp.tool()
def memory_import(path: str) -> str:
    """Import a .mempack file into the current profile (verified + sanitized)."""
    sha = store.import_pack(Path(path), _profile())
    return f"imported as commit {sha[:8]}"


@mcp.tool()
def memory_list_nodes(filter: str | None = None) -> str:
    """List memory nodes, optionally filtered by substring."""
    q = (filter or "").lower()
    out = [
        {
            "id": n.id,
            "part": part,
            "text": n.text,
            "granularity": n.granularity,
            "salience": n.salience,
            "superseded": n.superseded_by is not None,
        }
        for part, nodes in _parts().items()
        for n in nodes
        if q in n.text.lower()
    ]
    return json.dumps(out, indent=2)


def _parts() -> dict[str, list[SemanticNode]]:
    p = _pack()
    return {"identity": p.identity, "episodes": p.episodes, "threads": p.threads}


def serve() -> None:
    mcp.run()  # stdio transport
