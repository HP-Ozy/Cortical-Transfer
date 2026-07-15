"""Optional RAG over raw history chunks (requires `cortical-transfer[rag]` / chromadb).

The Chroma index lives in `<pack>/.rag/` next to the pack and is derived data:
it is never part of the MemPack format, never hashed, never committed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INDEX_DIR = ".rag"


def _collection(pack_path: Path, embedding_function: Any = None) -> Any:
    try:
        import chromadb
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "RAG requires the optional extra: pip install cortical-transfer[rag]"
        ) from e
    client = chromadb.PersistentClient(path=str(pack_path / INDEX_DIR))
    kwargs = {"embedding_function": embedding_function} if embedding_function else {}
    return client.get_or_create_collection("raw_history", **kwargs)


def index_raw(pack_path: Path, embedding_function: Any = None) -> int:
    """Index every turn in raw/*.jsonl. Returns number of chunks indexed."""
    col = _collection(pack_path, embedding_function)
    ids: list[str] = []
    docs: list[str] = []
    raw = pack_path / "raw"
    if raw.is_dir():
        for f in sorted(raw.glob("*.jsonl")):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines()):
                if not line.strip():
                    continue
                try:
                    content = str(json.loads(line).get("content", ""))
                except ValueError:
                    content = line
                if content.strip():
                    ids.append(f"{f.name}:{i}")
                    docs.append(content)
    if ids:
        col.upsert(ids=ids, documents=docs)
    return len(ids)


def search_raw(
    pack_path: Path, query: str, k: int = 5, embedding_function: Any = None
) -> list[str]:
    """Top-k raw chunks for `query`. Empty list if nothing indexed."""
    col = _collection(pack_path, embedding_function)
    if col.count() == 0:
        return []
    res = col.query(query_texts=[query], n_results=min(k, col.count()))
    return [str(d) for d in res["documents"][0]]
