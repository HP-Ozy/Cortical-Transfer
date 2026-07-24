# ADR 0005 — MCP: FastMCP over stdio, plain-function tools, substring search in core

Status: revived 2026-07-24 as the optional `[mcp]` extra
(`cortical_transfer/mcp_server.py`, entry point `ct-mcp`) — three tools
(memory_profile, memory_search, memory_add_fact) instead of the original six;
the rest of this ADR's design (FastMCP stdio, plain functions, `CT_PROFILE`,
substring search, sanitize at the boundary) applies as written. Core stays
dependency-free: `mcp` is not a base dependency.
Previously: superseded 2026-07-18 — MCP server and [rag] extra removed from
core to keep the project narrow. Date: 2026-07-15.

- Official `mcp` SDK's FastMCP with the six spec'd tools; stdio transport only
  (local-first, every MCP client supports it). No HTTP/SSE in v0.1.
- Tools are plain module functions decorated with `@mcp.tool()` — directly
  callable in tests without an MCP client round-trip.
- `memory_search` is case-insensitive substring over node text and tags.
  Semantic search belongs to the optional [rag] extra and operates on raw
  history, not nodes; for a few hundred nodes substring is adequate and
  dependency-free. Upgrade path: route through Chroma when the extra is
  present, same tool signature.
- Profile selection via `CT_PROFILE` env var — MCP client configs can set env
  per server entry; no per-call profile parameter to keep tool surfaces small.
- `memory_add_fact` sanitizes on the way in and `memory_import` verifies +
  sanitizes: MCP is a trust boundary like any other import path.
