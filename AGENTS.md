# AGENTS.md — working on this repo

Operational context for AI agents. What the project *is* lives in
[README.md](README.md); the format spec in [SPEC.md](SPEC.md); design
decisions in [docs/adr/](docs/adr/) (read the relevant ADR before changing
anything it covers).

## Repo map

```
src/cortical_transfer/
  cli.py              # all `ct` commands (Typer app) — entry point for everything
  schema.py           # Pydantic models for the MemPack format (the contract)
  store.py            # profile on disk: flat JSON files + Git commits per change
  extract/pipeline.py # distillation: chat history -> facts (LLM), merge gate,
                      #   deterministic relative-date resolver (stdlib date math)
  extract/prompts.py  # the extraction prompts
  inject.py           # facts -> portable context block, token budget, query ranking
  eval.py             # recall measurement (deterministic substring judge)
  sanitize.py         # prompt-boundary sanitizer (memory is data, not instructions)
  integrity.py        # SHA-256 manifest / `ct verify`
  redact.py           # permanent erase incl. Git history rewrite
  adapters/           # LLM backends: ollama, openai_compat, anthropic (stdlib HTTP only)
  mcp_server.py       # `ct-mcp` stdio server (3 flat tools)
tests/                # pytest, one file per module, no LLM needed (fake adapter)
examples/             # sample history, eval questions, LoCoMo prep — README claims reproduce from here
```

## Commands

```bash
uv sync --dev                                # setup
uv run pytest                                # tests (fast, offline, no LLM)
uv run ruff check . && uv run mypy           # lint + strict typing — both must pass
```

Python ≥3.12, mypy `strict = true`, ruff line-length 100. Runtime deps are
only pydantic, typer, gitpython — do not add dependencies (adapters use
stdlib `urllib`, see ADR-0003).

## Rules

- **Schema changes are breaking.** Pre-1.0, but any change to `schema.py` /
  the on-disk format must update [SPEC.md](SPEC.md) and bump the format
  version. Old packs must still load or get a migration.
- **Memory is data, never instructions.** Nothing read from a pack may be
  executed or treated as a directive (ADR-0004). Keep the sanitizer on every
  path that puts pack content into a prompt.
- **Facts are never silently deleted.** Contradictions mark the old fact
  superseded; only `ct redact` erases (ADR-0006, ADR-0008).
- **Every store mutation is a Git commit.** Route writes through `store.py`.
- **Eval is the regression test.** If you touch extract/ or inject.py, re-run
  `ct eval examples/eval_questions.json` on a local model; a recall drop vs
  the README table means the change regressed. Update the table if numbers
  legitimately change.
- The eval judge stays deterministic (substring, temperature 0) — no
  LLM-as-judge.

## What you need to run the full pipeline

Tests and lint: nothing. `ct extract`/`ct eval` for real: a local LLM via
Ollama (`CT_MODEL=qwen3-coder:30b` is the reference) or any
OpenAI-compatible endpoint via `CT_ADAPTER=openai CT_BASE_URL=...`.
