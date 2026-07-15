# ADR 0001 — Format: flat JSON arrays + inline ULID, hashes exclude the manifest

Status: accepted. Date: 2026-07-15.

## Decisions

1. **Part files are flat JSON arrays of SemanticNode** (no wrapper object).
   Simplest thing a third-party importer can parse; extension happens by adding
   files or optional node fields, both covered by the §8 migration policy.
2. **ULID generated inline** (~10 lines, Crockford base32) instead of adding a
   `python-ulid` dependency. Monotonicity within the same millisecond is not
   guaranteed and not needed — ids only need uniqueness, ordering comes from
   timestamps.
3. **`content_hashes` lives in `mempack.json` and excludes it** — a file cannot
   contain its own hash. Consequence: the manifest itself is not
   tamper-evident in v0.1. Accepted: integrity targets corruption, not
   adversaries; signing is deferred to a future version (SPEC §5).
4. **Datetimes serialized by Pydantic as RFC 3339** — no custom encoders.

## Dependencies introduced (stack-mandated, recorded here once)

pydantic (schemas are the product), typer (CLI), mcp (server), gitpython
(store). Dev: pytest, pytest-cov, ruff, mypy. Everything else is stdlib.
