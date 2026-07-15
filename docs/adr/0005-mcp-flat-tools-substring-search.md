# ADR 0005 — MCP: FastMCP over stdio, plain-function tools, substring search in core

Status: accepted. Date: 2026-07-15.

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
