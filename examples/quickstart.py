"""Quickstart: extract memory from "model A" chats, inject into "model B".

Requires a running LLM (default: Ollama at localhost:11434).
Pick the model with CT_MODEL, e.g.:  CT_MODEL=llama3.1:8b python examples/quickstart.py
"""

from pathlib import Path

from cortical_transfer.adapters.base import get_adapter
from cortical_transfer.extract.pipeline import extract
from cortical_transfer.inject import build_context
from cortical_transfer.integrity import load_pack, save_pack

HISTORY = Path(__file__).parent / "sample_history.jsonl"
PACK_DIR = Path("dana.mempack.d")

# 1. Extract: chat history from "model A" -> MemPack
pack = extract(HISTORY, get_adapter())
save_pack(pack, PACK_DIR)
print(f"extracted {len(pack.all_nodes())} nodes -> {PACK_DIR}/")

# 2. Inject: MemPack -> context block for "model B" (any vendor, any model)
context = build_context(load_pack(PACK_DIR), budget_tokens=2000)
print("\n--- paste this into model B's system prompt ---\n")
print(context)
