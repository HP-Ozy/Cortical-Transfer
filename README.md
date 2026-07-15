# Cortical-Transfer

> **Your AI experience follows you. Not the model.**

*(Manifesto placeholder — final text to be supplied. The mission, meanwhile:)*

Every time you switch LLMs — new vendor, new model, new app — you start from
zero. The assistant that knew your stack, your projects, your tone, is gone.
Cortical-Transfer makes your AI memory **portable**: an open, versioned,
human-readable file format (**MemPack**) plus a local-first toolchain to
extract it from your chat history, keep it under Git version control, and
inject it into any other model. No cloud, no accounts, no telemetry.

The product is two things, in this order:

1. **The MemPack format** — the standard. See [SPEC.md](SPEC.md).
2. **This reference implementation** — Python library + CLI (`ct`) + MCP server.

## 60-second quickstart

```bash
git clone https://github.com/you/cortical-transfer && cd cortical-transfer
uv sync                          # or: pip install -e .
# have Ollama running locally (default model: llama3.1:8b, override with CT_MODEL)

ct init                                      # create a Git-versioned memory profile
ct extract examples/sample_history.jsonl     # chat history -> MemPack, committed
ct inspect                                   # pretty-print your memory
ct inject --budget 2000 > context.txt        # portable context block for ANY model
ct verify                                    # SHA-256 integrity check
ct export my_memory.mempack                  # one portable file
ct import my_memory.mempack --profile new-model
```

`context.txt` is a plain-text block you paste (or pipe) into any model's
system prompt — GPT, Claude, Gemini, a local model, anything. That's the
transfer.

Other commands: `ct log`, `ct diff <rev> <rev>`, `ct checkout <rev>`,
`ct redact <node-id>`, `ct mcp serve`. Adapter selection: `CT_ADAPTER=ollama`
(default) or `CT_ADAPTER=openai` + `CT_BASE_URL`/`CT_API_KEY`/`CT_MODEL`
(works with any OpenAI-compatible endpoint).

## What it does today vs. the vision

**Today (v0.1)** is deliberately *text-based portability*:

- Extracts identity facts, salient episodes, open threads, and an interaction
  style card from chat-history JSONL, using a local LLM by default.
- Stores them as a Git repo: every update is a commit, `ct diff` shows memory
  changes semantically, `ct checkout` restores any previous state.
- Injects them as a token-budgeted, clearly-delimited context block.
- Contradictions are never silently deleted: the older fact is marked
  superseded and kept.
- `ct redact` permanently erases a node — including from Git history
  (see limits in [SPEC.md §7](SPEC.md) and `docs/adr/0006`).

**Explicitly out of scope for v0.1:** soft prompts, embedding injection,
latent-space projectors, fine-tuning, any cloud service, any UI. The vision —
richer transfer mechanisms as models expose better interfaces — sits on top of
the same format. The format is the bet; today's injection is just its first
consumer.

## The MemPack format

A MemPack is one directory (or a zipped `.mempack`):

| File | Content |
|------|---------|
| `mempack.json` | manifest: format version, timestamps, source models, SHA-256 of every file |
| `identity.json` | stable facts about you |
| `episodes.json` | salient events and decisions, hierarchical, salience-scored |
| `threads.json` | open/unresolved topics |
| `style.md` | how you like to interact, in plain Markdown |
| `raw/` | *(optional)* original history chunks for provenance |

Everything is human-readable JSON/Markdown. Security model: memory is **data,
not instructions** — importers must never execute what's inside a node, and
this implementation neutralizes instruction-like payloads at the prompt
boundary. Full field semantics, versioning policy, integrity rules, and a
minimal conforming example: **[SPEC.md](SPEC.md)** — written so you can build
an importer in any language without reading our code.

## MCP server

Expose your memory to any MCP-capable client (Claude Desktop, IDEs, ...):

```bash
ct mcp serve        # stdio
```

Claude Desktop — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cortical-transfer": {
      "command": "ct",
      "args": ["mcp", "serve"],
      "env": { "CT_PROFILE": "default" }
    }
  }
}
```

Any other MCP client: same idea — command `ct`, args `mcp serve`, optional
`CT_PROFILE` env var. Tools exposed: `memory_get_context`, `memory_search`,
`memory_add_fact`, `memory_export`, `memory_import`, `memory_list_nodes`.

## Optional RAG extra

```bash
pip install "cortical-transfer[rag]"    # or: uv sync --extra rag
```

Adds ChromaDB-backed retrieval over your raw history chunks:
`ct inject --query "that postgres migration"` appends the most relevant raw
excerpts to the context block. The core library never requires it.

## Development

```bash
uv sync --dev --extra rag
uv run pytest && uv run ruff check . && uv run mypy
```

Design decisions live in [docs/adr/](docs/adr/). License: Apache-2.0.
