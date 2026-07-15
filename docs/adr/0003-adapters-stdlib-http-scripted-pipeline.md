# ADR 0003 — Adapters over stdlib urllib; pipeline applies LLM proposals deterministically

Status: accepted. Date: 2026-07-15.

## HTTP client: stdlib `urllib`, no SDK dependencies

Both adapters need exactly one blocking POST with a JSON body. `urllib.request`
does that in ~10 lines; adding `httpx`/`openai`/`ollama` SDKs would buy retries
and streaming we don't use in v0.1. Revisit if we ever stream tokens.

## Pipeline shape: LLM proposes, code disposes

Every LLM output is treated as an untrusted *proposal* parsed defensively:

- Per-conversation extraction returns candidate nodes; a malformed response
  drops that one conversation, never the run.
- Dedup happens in two stages: exact normalized-text merge (pure code, free),
  then an LLM pass per category, chunked at 40 statements
  (`_RESOLVE_CHUNK` — keeps prompts small on 8B local models).
- Contradictions are applied by `apply_resolution`, which validates indices
  and only ever sets `superseded_by` — deletion is impossible by construction
  (SPEC §3).
- Salience comes from the extraction prompt itself; no separate scoring pass
  (one more LLM round-trip per node for marginal gain).

## Streaming

`iter_conversations` streams contiguous `conversation_id` runs via
`itertools.groupby` — only one conversation's turns are in memory at a time.
A non-contiguous id yields two runs; downstream dedup merges the results, so
correctness degrades to extra LLM calls, not wrong output.

Rejected: full-history single prompt (blows context), embedding-based dedup in
core (Chroma is an optional extra; core must work without it).
