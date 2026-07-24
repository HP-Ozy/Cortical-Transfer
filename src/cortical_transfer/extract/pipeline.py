"""Chat history (JSONL) -> MemPack. Streams one conversation at a time."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
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
_MERGE_CHUNK = 20  # new candidates per merge-gate call (existing list rides along whole)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _conv_date(turns: list[Turn]) -> str | None:
    """First parseable turn timestamp as YYYY-MM-DD (unix float or ISO)."""
    for t in turns:
        if not t.timestamp:
            continue
        for parse in (
            lambda s: datetime.fromtimestamp(float(s), UTC),
            datetime.fromisoformat,
        ):
            try:
                return parse(t.timestamp).date().isoformat()
            except ValueError:
                continue
    return None


def _iso_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and _ISO_DATE.match(value) else None


# "tomorrow", "last week", "3 months ago", ... — not already followed by a (... year) date
_RELATIVE = re.compile(
    r"\b(?:(yesterday|today|tomorrow)"
    r"|(last|next|this)\s+(week|weekend|month|year)"
    r"|(\d{1,3}|an?)\s+(day|week|month|year)s?\s+ago)\b(?!\s*\([^)]*\d{4}[^)]*\))",
    re.IGNORECASE,
)


def _day(d: date) -> str:
    return f"{d.day} {d:%B} {d.year}"  # "9 May 2023" — unambiguous, no DD/MM vs MM/DD


def _month_shift(d: date, months: int) -> str:
    m = d.year * 12 + d.month - 1 + months
    return f"{date(m // 12, m % 12 + 1, 1):%B} {m // 12}"


def resolve_relative_dates(text: str, conv_date: str | None) -> str:
    """Append the absolute date to relative expressions: "tomorrow" -> "tomorrow (9 May 2023)".

    Deterministic (stdlib date math against the conversation's date), so temporal
    recall no longer depends on the extractor model resolving "last week" itself —
    the measured weak spot on LoCoMo. Day/week resolve to a day, month/year to
    their coarser period ("last month" -> "(April 2023)"). Spelled-out English
    dates, not ISO: readers echo the annotation verbatim, and "(2023-06-29)" is
    opaque to a human (and to a substring judge) where "29 June 2023" is not."""
    if not conv_date:
        return text
    base = date.fromisoformat(conv_date)

    def resolved(m: re.Match[str]) -> str:
        if m[1]:
            days = {"yesterday": -1, "today": 0, "tomorrow": 1}[m[1].lower()]
            return _day(base + timedelta(days=days))
        if m[2]:
            step = {"last": -1, "this": 0, "next": 1}[m[2].lower()]
            unit = m[3].lower()
            if unit in ("week", "weekend"):  # ponytail: weekend ~ week shift, day precision
                return _day(base + timedelta(weeks=step))
            return _month_shift(base, step) if unit == "month" else str(base.year + step)
        n = 1 if m[4].lower() in ("a", "an") else int(m[4])
        unit = m[5].lower()
        if unit in ("day", "week"):
            return _day(base - timedelta(days=n * (7 if unit == "week" else 1)))
        return _month_shift(base, -n) if unit == "month" else str(base.year - n)

    return _RELATIVE.sub(lambda m: f"{m[0]} ({resolved(m)})", text)


def _candidate_nodes(
    adapter: Adapter, conv_id: str, turns: list[Turn]
) -> dict[str, list[SemanticNode]]:
    transcript = "\n".join(f"[{t.turn_id}] {t.role}: {t.content}" for t in turns)
    conv_date = _conv_date(turns)
    raw = adapter.complete(
        prompts.EXTRACT_NODES_V3.format(
            conversation_id=conv_id,
            conversation_date=conv_date or "unknown",
            transcript=transcript[:_TRANSCRIPT_CAP],
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
                        text=resolve_relative_dates(str(item["text"]), conv_date),
                        granularity=item.get("granularity", "episode"),
                        salience=max(0.0, min(1.0, float(item.get("salience", 0.5)))),
                        confidence=(
                            "inferred" if item.get("confidence") == "inferred" else "stated"
                        ),
                        tags=[str(t) for t in item.get("tags", [])],
                        valid_from=_iso_or_none(item.get("valid_from")),
                        valid_until=_iso_or_none(item.get("valid_until")),
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
            if n.confidence == "stated":
                kept.confidence = "stated"
            kept.source_refs = list(dict.fromkeys(kept.source_refs + n.source_refs))
            kept.tags = list(dict.fromkeys(kept.tags + n.tags))
            kept.last_confirmed_at = max(kept.last_confirmed_at, n.last_confirmed_at)
            kept.valid_from = kept.valid_from or n.valid_from
            kept.valid_until = n.valid_until or kept.valid_until
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
            prompts.RESOLVE_V2.format(numbered=numbered), system=prompts.SYSTEM_V1, json_mode=True
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


def apply_merge(
    base: list[SemanticNode],
    new: list[SemanticNode],
    duplicates: list[list[int]],
    contradictions: list[list[int]],
) -> list[SemanticNode]:
    """Deterministically apply LLM-proposed [existing, new] pairs.

    Duplicate: fold the new node into the existing one (keep the richer text,
    union refs/tags — the mem0 "keep the most information" rule). Contradiction:
    mark the existing node superseded by the new one (SPEC §3); the superseded
    fact inherits its end date from the new fact's start (graphiti rule)."""
    eb, nb = range(len(base)), range(len(new))
    folded: set[int] = set()
    for pair in duplicates:
        if len(pair) == 2 and pair[0] in eb and pair[1] in nb and pair[1] not in folded:
            old, cand = base[pair[0]], new[pair[1]]
            if len(cand.text) > len(old.text):
                old.text = cand.text
            old.salience = max(old.salience, cand.salience)
            if cand.confidence == "stated":
                old.confidence = "stated"
            old.source_refs = list(dict.fromkeys(old.source_refs + cand.source_refs))
            old.tags = list(dict.fromkeys(old.tags + cand.tags))
            old.last_confirmed_at = max(old.last_confirmed_at, cand.last_confirmed_at)
            old.valid_from = old.valid_from or cand.valid_from
            old.valid_until = cand.valid_until or old.valid_until
            folded.add(pair[1])
    for pair in contradictions:
        if len(pair) == 2 and pair[0] in eb and pair[1] in nb and pair[1] not in folded:
            old, cand = base[pair[0]], new[pair[1]]
            if not old.superseded_by:
                old.superseded_by = cand.id
                old.valid_until = old.valid_until or cand.valid_from
    return base + [n for i, n in enumerate(new) if i not in folded]


def merge_with_base(
    adapter: Adapter, base: list[SemanticNode], new: list[SemanticNode]
) -> list[SemanticNode]:
    """Gate NEW nodes against the existing live memory: fold duplicates,
    supersede contradictions, add the rest. A failed LLM call keeps everything
    (fail open — never lose information)."""
    if not base or not new:
        return base + new
    out = base
    for i in range(0, len(new), _MERGE_CHUNK):
        chunk = new[i : i + _MERGE_CHUNK]
        raw = adapter.complete(
            prompts.MERGE_V1.format(
                existing="\n".join(f"{j}. {n.text}" for j, n in enumerate(out)),
                new="\n".join(f"{j}. {n.text}" for j, n in enumerate(chunk)),
            ),
            system=prompts.SYSTEM_V1,
            json_mode=True,
        )
        try:
            data = parse_json(raw)
            out = apply_merge(
                out, chunk, data.get("duplicates", []), data.get("contradictions", [])
            )
        except (ValueError, json.JSONDecodeError):
            out = out + chunk
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


def _conv_digest(turns: list[Turn]) -> str:
    return hashlib.sha256(
        "\n".join(f"{t.role}:{t.content}" for t in turns).encode("utf-8")
    ).hexdigest()


def extract(
    history: Path,
    adapter: Adapter,
    source_model: str | None = None,
    base: MemPack | None = None,
    force: bool = False,
) -> MemPack:
    """Full pipeline: candidates -> dedup -> contradictions -> merge into base
    -> hierarchy -> style. With a `base` pack, new facts are gated against the
    existing memory (fold duplicates, supersede contradictions) instead of
    starting from scratch. Conversations already distilled into `base` (same
    id, same content) are skipped — no LLM calls — unless `force` is set."""
    base = base or MemPack()
    seen = dict(base.manifest.extracted)
    parts: dict[str, list[SemanticNode]] = {"identity": [], "episodes": [], "threads": []}
    user_sample: list[str] = []
    for conv_id, turns in iter_conversations(history):
        digest = _conv_digest(turns)
        if not force and seen.get(conv_id) == digest:
            continue
        seen[conv_id] = digest
        for part, nodes in _candidate_nodes(adapter, conv_id, turns).items():
            parts[part].extend(nodes)
        if sum(map(len, user_sample)) < _STYLE_CAP:
            user_sample += [t.content for t in turns if t.role == "user"]

    for part in parts:
        fresh = _resolve(adapter, dedup_exact(parts[part]))
        old: list[SemanticNode] = getattr(base, part)
        live = [n for n in old if not n.superseded_by]
        dead = [n for n in old if n.superseded_by]
        # exact-text repeats confirm the existing node for free (no LLM call)
        live_ids = {n.id for n in live}
        combined = dedup_exact(live + fresh)
        parts[part] = dead + merge_with_base(
            adapter,
            [n for n in combined if n.id in live_ids],
            [n for n in combined if n.id not in live_ids],
        )
    # group only ungrouped episode nodes; existing summaries/children stay as-is
    loose = [n for n in parts["episodes"] if n.granularity != "summary" and not n.parent_id]
    kept = [n for n in parts["episodes"] if n.granularity == "summary" or n.parent_id]
    parts["episodes"] = build_hierarchy(adapter, loose) + kept

    style = (
        adapter.complete(
            prompts.STYLE_V1.format(messages="\n---\n".join(user_sample)[:_STYLE_CAP])
        ).strip()
        if user_sample
        else ""
    )

    pack = MemPack(
        manifest=base.manifest,
        identity=parts["identity"],
        episodes=parts["episodes"],
        threads=parts["threads"],
        style=style or base.style,
    )
    pack.manifest.extracted = seen
    model = source_model or str(getattr(adapter, "model", adapter.name))
    pack.manifest.source_models = list(dict.fromkeys(pack.manifest.source_models + [model]))
    return pack
