# ADR 0008 — Extract merges through a gate; facts carry real-world validity

Status: accepted. Date: 2026-07-20.

## Problem

`ct extract` rebuilt the pack from the given history alone: running it on a
second export silently replaced the accumulated memory, and a contradiction
between old and new facts was never detected because dedup/contradiction ran
only within a single run. Facts also had no notion of *when they were true in
the world* — only Git ingestion time — so "moved to Milan last month" and
"lives in Turin" could both sit live in the context block.

## Decision

Two changes, both surveyed from mem0 / graphiti / zep / cognee and reduced to
their plain-text core (no embeddings, no graph DB):

1. **Merge gate.** `extract()` takes the existing pack as `base`. New
   candidates are resolved among themselves as before, then gated against the
   live base nodes with one LLM call per ~20 candidates (`MERGE_V1`): a
   duplicate is folded into the existing node (richer text wins, refs/tags
   union — mem0's "keep the most information"), a contradiction marks the
   existing node `superseded_by` the new one (SPEC §3), anything else is
   added. Exact-text repeats are folded for free before the LLM sees them.
   A failed call keeps both sides — fail open, never lose memory.

2. **Temporal validity.** `SemanticNode` gains optional `valid_from` /
   `valid_until` (ISO dates, event time — distinct from `created_at`,
   ingestion time; graphiti's bi-temporal pair, minus the graph). The
   extraction prompt resolves relative expressions against the conversation's
   own date and forbids invented bounds. A superseded fact inherits
   `valid_until` from its successor's `valid_from`. `inject` skips expired
   facts and prints ranges as `(valid FROM -> now)`; format bumped to 0.2.0.

## Rejected

- Retrieval infrastructure (vectors, BM25, graphs): the pack fits in the
  context window by design — there is nothing to retrieve from.
- Full bi-temporal bookkeeping (`expired_at` on top of Git): Git commit
  history already is the transaction timeline.
- Re-resolving the whole base every run: only new candidates pass the gate;
  cost scales with the new history, not with accumulated memory.
