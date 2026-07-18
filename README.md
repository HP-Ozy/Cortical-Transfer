# Cortical-Transfer

> **Transport your AI identity, not just your prompts.**

<img width="1402" height="1122" alt="Cortical-Transfer" src="https://github.com/user-attachments/assets/ad3082d9-acec-491b-b0eb-31aa6e943b60" />

---

## Introduction

Less than ten years ago I discovered Machine Learning.

From that moment, I fell in love with every topic I studied, learned, and applied.

However, there has always been one thing that never felt right to me and that made me distrust AI systems such as chatbots, algorithms, and intelligent assistants:

> **The lack of portability of user experience.**

In 2022, ChatGPT-3 was released.

At the time, it was a truly revolutionary product.

Yet that same feeling never disappeared.

Every time a better model came out, I had to start over.

I had to rebuild my context, my preferences, my working style, and everything the previous model had learned about me.

Today I want to help make that feeling disappear.

That's why I created **Cortical-Transfer**.

---

## What is Cortical-Transfer?

**Cortical-Transfer** is an open-source library that can be integrated into chatbots and AI agents.

Its goal is simple:

> **Allow users to carry their AI identity, memory, context, and experience from one model to another without starting over.**

Imagine using an AI model for years. It learns how you work. It understands
your preferences. It remembers your projects. Then a new state-of-the-art
model is released. With Cortical-Transfer, switching models shouldn't mean
losing years of accumulated experience.

Your AI experience follows you. Not the model.

The product is two things, in this order:

1. **The MemPack format** — the standard. See [SPEC.md](SPEC.md).
2. **This reference implementation** — Python library + CLI (`ct`) + MCP server.

## The mechanism, in one sentence

Every LLM — GPT, Claude, DeepSeek, Qwen, a local model — natively understands
one format: **plain text in its context window**. So the whole transfer
mechanism reduces to this: distill the user's experience into a
self-describing, human-readable text block whose *header is itself a prompt*
telling the receiving model how to use what follows. No APIs between vendors,
no embeddings, no fine-tuning required. The file **is** the protocol.

The smallest working proof of this idea is a single markdown file:
[`examples/passport-skill.md`](examples/passport-skill.md) — an agent skill
that exports a live session (plus long-term, cross-session memory) as a
`PASSPORT.md` you paste as the first message into any other model, which then
resumes the work knowing who you are, what you asked, and where things stand.
Cortical-Transfer is that same mechanism made rigorous: a versioned schema
instead of freeform prose, integrity checks, Git history, token budgeting,
and a prompt-boundary sanitizer.

## 60-second quickstart

```bash
git clone https://github.com/HP-Ozy/Cortical-Transfer && cd Cortical-Transfer
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
