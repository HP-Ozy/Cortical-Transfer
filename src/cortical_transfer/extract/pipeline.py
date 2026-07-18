"""Chat history (JSONL) -> MemPack. Streams one conversation at a time."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from itertools import groupby
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from cortical_transfer.adapters.base import Adapter
from cortical_transfer.extract import prompts
from cortical_transfer.schema import MemPack, SemanticNode

_TRANSCRIPT_CAP = 12_000  # chars per conversation sent to the LLM
_STYLE_CAP = 8_000  # chars of user messages for the style card
_RESOLVE_CHUNK = 40  # statements per dedup/contradiction call


class Turn(BaseModel):
    role: str
    content: str
    timestamp: str | None = None
    conversation_id: str
    turn_id: str


def iter_conversations(path: Path) -> Iterator[tuple[str, list[Turn]]]:
    """Stream conversations, one at a time.

    Accepts native JSONL (contiguous conversation_id runs) or a real-world
    `conversations.json` export from ChatGPT or Claude, auto-detected per
    conversation object.
    """
    if path.suffix == ".json":
        for i, conv in enumerate(json.loads(path.read_text(encoding="utf-8"))):
            turns = _chatgpt_turns(conv, i) if "mapping" in conv else _claude_turns(conv, i)
            if turns:
                yield turns[0].conversation_id, turns
        return

    def turns_() -> Iterator[Turn]:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield Turn.model_validate_json(line)

    for conv_id, group in groupby(turns_(), key=lambda t: t.conversation_id):
        yield conv_id, list(group)


def _chatgpt_turns(conv: dict[str, Any], idx: int) -> list[Turn]:
    """One conversation from a ChatGPT export: walk the active branch
    (current_node -> parents), keep non-empty user/assistant text parts."""
    conv_id = str(conv.get("id") or conv.get("conversation_id") or f"chatgpt-{idx}")
    mapping = conv.get("mapping") or {}
    chain: list[dict[str, Any]] = []
    node_id = conv.get("current_node")
    while node_id:
        node = mapping.get(node_id) or {}
        if node.get("message"):
            chain.append(node["message"])
        node_id = node.get("parent")
    turns: list[Turn] = []
    for msg in reversed(chain):
        role = (msg.get("author") or {}).get("role")
        parts = (msg.get("content") or {}).get("parts") or []
        text = "\n".join(p for p in parts if isinstance(p, str) and p.strip())
        if role not in ("user", "assistant") or not text:
            continue  # system/tool noise, multimodal stubs, empty roots
        ts = msg.get("create_time")
        turns.append(
            Turn(
                role=role,
                content=text,
                timestamp=str(ts) if ts else None,
                conversation_id=conv_id,
                turn_id=str(msg.get("id") or f"{conv_id}:{len(turns)}"),
            )
        )
    return turns


def _claude_turns(conv: dict[str, Any], idx: int) -> list[Turn]:
    """One conversation from a Claude (claude.ai) export."""
    conv_id = str(conv.get("uuid") or f"claude-{idx}")
    roles = {"human": "user", "assistant": "assistant"}
    turns: list[Turn] = []
    for m in conv.get("chat_messages") or []:
        role = roles.get(m.get("sender", ""))
        text = (m.get("text") or "").strip()
        if not role or not text:
            continue
        turns.append(
            Turn(
                role=role,
                content=text,
                timestamp=m.get("created_at"),
                conversation_id=conv_id,
                turn_id=str(m.get("uuid") or f"{conv_id}:{len(turns)}"),
            )
        )
    return turns


def parse_json(text: str) -> Any:
    """Tolerant JSON parse: strips fences/prose around the first JSON value."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=0)
    return json.loads(text[start:])


def _candidate_nodes(
    adapter: Adapter, conv_id: str, turns: list[Turn]
) -> dict[str, list[SemanticNode]]:
    transcript = "\n".join(f"[{t.turn_id}] {t.role}: {t.content}" for t in turns)
    raw = adapter.complete(
        prompts.EXTRACT_NODES_V1.format(
            conversation_id=conv_id, transcript=transcript[:_TRANSCRIPT_CAP]
        ),
        system=prompts.SYSTEM_V1,
        json_mode=True,
    )
    refs = [t.turn_id for t in turns]
    out: dict[str, list[SemanticNode]] = {"identity": [], "episodes": [], "threads": []}
    try:
        data = parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        return out  # a malformed response loses one conversation, not the run
    for part in out:
        for item in data.get(part, []) or []:
            try:
                out[part].append(
                    SemanticNode(
                        text=str(item["text"]),
                        granularity=item.get("granularity", "episode"),
                        salience=max(0.0, min(1.0, float(item.get("salience", 0.5)))),
                        tags=[str(t) for t in item.get("tags", [])],
                        source_refs=refs,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return out


def dedup_exact(nodes: list[SemanticNode]) -> list[SemanticNode]:
    """Merge nodes with identical normalized text (keep max salience, union refs/tags)."""
    seen: dict[str, SemanticNode] = {}
    for n in nodes:
        key = re.sub(r"\W+", " ", n.text.lower()).strip()
        if key in seen:
            kept = seen[key]
            kept.salience = max(kept.salience, n.salience)
            kept.source_refs = list(dict.fromkeys(kept.source_refs + n.source_refs))
            kept.tags = list(dict.fromkeys(kept.tags + n.tags))
            kept.last_confirmed_at = max(kept.last_confirmed_at, n.last_confirmed_at)
        else:
            seen[key] = n
    return list(seen.values())


def apply_resolution(
    nodes: list[SemanticNode], duplicates: list[list[int]], contradictions: list[list[int]]
) -> list[SemanticNode]:
    """Deterministically apply LLM-proposed pairs. Duplicates: drop. Contradictions:
    mark the older node superseded_by the newer — never delete (SPEC §3)."""
    valid = range(len(nodes))
    drop = {d for pair in duplicates if len(pair) == 2 and pair[1] in valid for d in [pair[1]]}
    for pair in contradictions:
        if len(pair) == 2 and pair[0] in valid and pair[1] in valid and pair[0] != pair[1]:
            nodes[pair[0]].superseded_by = nodes[pair[1]].id
    return [n for i, n in enumerate(nodes) if i not in drop]


def _resolve(adapter: Adapter, nodes: list[SemanticNode]) -> list[SemanticNode]:
    out: list[SemanticNode] = []
    for i in range(0, len(nodes), _RESOLVE_CHUNK):
        chunk = nodes[i : i + _RESOLVE_CHUNK]
        numbered = "\n".join(f"{j}. {n.text}" for j, n in enumerate(chunk))
        raw = adapter.complete(
            prompts.RESOLVE_V1.format(numbered=numbered), system=prompts.SYSTEM_V1, json_mode=True
        )
        try:
            data = parse_json(raw)
            chunk = apply_resolution(
                chunk, data.get("duplicates", []), data.get("contradictions", [])
            )
        except (ValueError, json.JSONDecodeError):
            pass
        out.extend(chunk)
    return out


def build_hierarchy(adapter: Adapter, episodes: list[SemanticNode]) -> list[SemanticNode]:
    """Group episodes under new summary parent nodes."""
    if len(episodes) < 4:
        return episodes
    numbered = "\n".join(f"{j}. {n.text}" for j, n in enumerate(episodes))
    raw = adapter.complete(
        prompts.HIERARCHY_V1.format(numbered=numbered), system=prompts.SYSTEM_V1, json_mode=True
    )
    try:
        groups = parse_json(raw).get("groups", [])
    except (ValueError, json.JSONDecodeError):
        return episodes
    parents: list[SemanticNode] = []
    for g in groups:
        members = [episodes[i] for i in g.get("members", []) if 0 <= i < len(episodes)]
        if len(members) < 2 or not g.get("summary"):
            continue
        parent = SemanticNode(
            text=str(g["summary"]),
            granularity="summary",
            salience=max(m.salience for m in members),
            source_refs=list(dict.fromkeys(r for m in members for r in m.source_refs)),
        )
        for m in members:
            m.parent_id = parent.id
        parents.append(parent)
    return parents + episodes


def extract(history: Path, adapter: Adapter, source_model: str | None = None) -> MemPack:
    """Full pipeline: candidates -> dedup -> contradictions -> hierarchy -> style."""
    parts: dict[str, list[SemanticNode]] = {"identity": [], "episodes": [], "threads": []}
    user_sample: list[str] = []
    for conv_id, turns in iter_conversations(history):
        for part, nodes in _candidate_nodes(adapter, conv_id, turns).items():
            parts[part].extend(nodes)
        if sum(map(len, user_sample)) < _STYLE_CAP:
            user_sample += [t.content for t in turns if t.role == "user"]

    for part in parts:
        parts[part] = _resolve(adapter, dedup_exact(parts[part]))
    parts["episodes"] = build_hierarchy(adapter, parts["episodes"])

    style = adapter.complete(
        prompts.STYLE_V1.format(messages="\n---\n".join(user_sample)[:_STYLE_CAP])
    ).strip()

    pack = MemPack(
        identity=parts["identity"],
        episodes=parts["episodes"],
        threads=parts["threads"],
        style=style,
    )
    pack.manifest.source_models = [source_model or str(getattr(adapter, "model", adapter.name))]
    return pack
