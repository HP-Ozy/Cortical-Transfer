# ADR 0007 — Synthetic example dataset with a planted contradiction

Status: accepted. Date: 2026-07-16.

`examples/sample_history.jsonl` is a hand-written 10-conversation history for
a fictional data engineer ("Dana"). Design choices:

- **Planted contradiction:** conv-03 (2025-11, "pandas for everything") vs
  conv-02 (2026-01, "polars is our standard now") — exercises the
  supersession path on real extractions.
- **Planted open threads:** GDPR legal review, 4-day-week pitch, duckdb
  exploration — exercises `threads.json`.
- **Planted style signals:** "keep answers short", English preference,
  espresso sign-off — exercises the style card.
- Hand-written rather than LLM-generated so the expected memory is known and
  reviewable in a PR diff.

The happy-path demo was verified end-to-end against live Ollama. Extraction
quality scales with the model — the default `llama3.1:8b` is the floor we
recommend; tiny models (1.5B) produce noisy nodes but never break the
pipeline (defensive JSON parsing, ADR 0003).
