import json
from pathlib import Path

from cortical_transfer.extract import prompts
from cortical_transfer.extract.pipeline import (
    Turn,
    _conv_date,
    apply_merge,
    apply_resolution,
    dedup_exact,
    extract,
    iter_conversations,
    merge_with_base,
    parse_json,
)
from cortical_transfer.schema import SemanticNode


class FakeAdapter:
    """Scripted adapter: routes by prompt type, no network."""

    name = "fake"
    model = "fake-1"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        if "CONVERSATION" in prompt:
            self.calls.append("extract")
            return json.dumps(
                {
                    "identity": [
                        {"text": "Works in AI", "granularity": "summary", "salience": 0.9}
                    ],
                    "episodes": [{"text": f"Episode {len(self.calls)}", "salience": 0.5}],
                    "threads": [],
                }
            )
        if "duplicates" in prompt:
            self.calls.append("resolve")
            return '{"duplicates": [], "contradictions": []}'
        if "groups" in prompt:
            self.calls.append("hierarchy")
            return '{"groups": []}'
        self.calls.append("style")
        return "Concise and technical."


def write_history(path: Path, n_convs: int = 3) -> Path:
    f = path / "history.jsonl"
    lines = []
    for c in range(n_convs):
        for t in range(2):
            lines.append(
                json.dumps(
                    {
                        "role": "user" if t % 2 == 0 else "assistant",
                        "content": f"message {c}-{t}",
                        "conversation_id": f"conv-{c}",
                        "turn_id": f"conv-{c}:{t}",
                    }
                )
            )
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


def test_iter_conversations_streams_groups(tmp_path: Path) -> None:
    f = write_history(tmp_path, n_convs=4)
    convs = list(iter_conversations(f))
    assert [c for c, _ in convs] == [f"conv-{i}" for i in range(4)]
    assert all(len(turns) == 2 for _, turns in convs)


def test_iter_conversations_chatgpt_export(tmp_path: Path) -> None:
    # active branch: root -> u1 -> a1; a0 is an abandoned edit, sys/empty skipped
    conv = {
        "id": "c1",
        "current_node": "a1",
        "mapping": {
            "root": {"message": None, "parent": None},
            "sys": {
                "message": {
                    "id": "m0",
                    "author": {"role": "system"},
                    "content": {"parts": ["you are helpful"]},
                },
                "parent": "root",
            },
            "u1": {
                "message": {
                    "id": "m1",
                    "author": {"role": "user"},
                    "content": {"parts": ["hello", {"image": "stub"}]},
                    "create_time": 1721000000.0,
                },
                "parent": "sys",
            },
            "a0": {
                "message": {
                    "id": "m2-old",
                    "author": {"role": "assistant"},
                    "content": {"parts": ["abandoned branch"]},
                },
                "parent": "u1",
            },
            "a1": {
                "message": {
                    "id": "m2",
                    "author": {"role": "assistant"},
                    "content": {"parts": ["hi there"]},
                },
                "parent": "u1",
            },
        },
    }
    f = tmp_path / "conversations.json"
    f.write_text(json.dumps([conv]), encoding="utf-8")
    convs = list(iter_conversations(f))
    assert len(convs) == 1
    conv_id, turns = convs[0]
    assert conv_id == "c1"
    assert [(t.role, t.content) for t in turns] == [("user", "hello"), ("assistant", "hi there")]
    assert turns[0].turn_id == "m1" and turns[0].timestamp == "1721000000.0"


def test_iter_conversations_claude_export(tmp_path: Path) -> None:
    conv = {
        "uuid": "abc",
        "chat_messages": [
            {"uuid": "t1", "sender": "human", "text": "ciao", "created_at": "2026-01-01"},
            {"uuid": "t2", "sender": "assistant", "text": "ciao!"},
            {"uuid": "t3", "sender": "human", "text": "   "},
        ],
    }
    f = tmp_path / "conversations.json"
    f.write_text(json.dumps([conv, {"uuid": "empty", "chat_messages": []}]), encoding="utf-8")
    convs = list(iter_conversations(f))
    assert len(convs) == 1  # empty conversation not yielded
    conv_id, turns = convs[0]
    assert conv_id == "abc"
    assert [(t.role, t.content) for t in turns] == [("user", "ciao"), ("assistant", "ciao!")]


def test_parse_json_tolerates_fences_and_prose() -> None:
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Here you go: {"a": [1, 2]}') == {"a": [1, 2]}


def test_dedup_exact_merges() -> None:
    a = SemanticNode(text="Uses uv.", salience=0.4, source_refs=["t1"], tags=["tools"])
    b = SemanticNode(text="uses uv", salience=0.8, source_refs=["t2"])
    merged = dedup_exact([a, b])
    assert len(merged) == 1
    assert merged[0].salience == 0.8
    assert merged[0].source_refs == ["t1", "t2"]


def test_contradiction_supersedes_not_deletes() -> None:
    old = SemanticNode(text="Uses pip")
    new = SemanticNode(text="Uses uv")
    out = apply_resolution([old, new], duplicates=[], contradictions=[[0, 1]])
    assert len(out) == 2  # nothing deleted
    assert out[0].superseded_by == new.id
    assert out[1].superseded_by is None


def test_apply_resolution_ignores_garbage_indices() -> None:
    nodes = [SemanticNode(text="a"), SemanticNode(text="b")]
    out = apply_resolution(nodes, duplicates=[[0, 99], [5]], contradictions=[[42, 0], [1, 1]])
    assert len(out) == 2 and all(n.superseded_by is None for n in out)


def test_extract_end_to_end(tmp_path: Path) -> None:
    f = write_history(tmp_path, n_convs=3)
    adapter = FakeAdapter()
    pack = extract(f, adapter)
    assert adapter.calls.count("extract") == 3
    assert "style" in adapter.calls
    assert len(pack.identity) == 1  # deduped across conversations
    assert len(pack.episodes) == 3
    assert pack.style == "Concise and technical."
    assert pack.manifest.source_models == ["fake-1"]
    assert all(n.source_refs for n in pack.all_nodes())


def test_prompt_version_pinned() -> None:
    assert prompts.PROMPT_VERSION == "v2"


def test_conv_date_parses_unix_and_iso() -> None:
    def turn(ts: str | None) -> Turn:
        return Turn(role="user", content="x", timestamp=ts, conversation_id="c", turn_id="c:0")

    assert _conv_date([turn("2026-01-05T09:12:00Z")]) == "2026-01-05"
    assert _conv_date([turn("1767571200")]) == "2026-01-05"
    assert _conv_date([turn(None), turn("garbage")]) is None


def test_apply_merge_folds_and_supersedes() -> None:
    base = [SemanticNode(text="Works as a data engineer"), SemanticNode(text="Uses pandas")]
    new = [
        SemanticNode(text="Works as a data engineer at a logistics startup"),
        SemanticNode(text="Uses polars now", valid_from="2026-03-01"),
        SemanticNode(text="Learning Rust"),
    ]
    out = apply_merge(base, new, duplicates=[[0, 0]], contradictions=[[1, 1]])
    assert len(out) == 4  # 2 base + 2 new; the duplicate was folded, nothing deleted
    assert out[0].text == "Works as a data engineer at a logistics startup"  # richer text wins
    assert out[1].superseded_by == new[1].id
    assert out[1].valid_until == "2026-03-01"  # superseded fact ends where the new one begins
    assert {n.text for n in out[2:]} == {"Uses polars now", "Learning Rust"}


class MergeFake:
    name = "fake"
    model = "fake-1"

    def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        assert "EXISTING:" in prompt and "NEW:" in prompt
        return '{"duplicates": [], "contradictions": [[0, 0]]}'


def test_merge_with_base_llm_gate() -> None:
    base = [SemanticNode(text="Standard dataframe library is pandas")]
    new = [SemanticNode(text="Standard dataframe library is polars", valid_from="2026-02-01")]
    out = merge_with_base(MergeFake(), base, new)
    assert len(out) == 2
    assert out[0].superseded_by == out[1].id
    assert out[0].valid_until == "2026-02-01"


def test_merge_with_base_skips_llm_when_either_side_empty() -> None:
    class Boom:
        name = "boom"

        def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
            raise AssertionError("no LLM call expected")

    node = SemanticNode(text="a")
    assert merge_with_base(Boom(), [], [node]) == [node]
    assert merge_with_base(Boom(), [node], []) == [node]


def test_extract_merges_into_base(tmp_path: Path) -> None:
    f = write_history(tmp_path, n_convs=1)

    class Adapter(FakeAdapter):
        def complete(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
            if "EXISTING:" in prompt:
                self.calls.append("merge")
                return '{"duplicates": [], "contradictions": [[0, 0]]}'
            return super().complete(prompt, system, json_mode)

    from cortical_transfer.schema import MemPack

    old = SemanticNode(text="Works in finance")
    base = MemPack(identity=[old])
    base.manifest.source_models = ["old-model"]
    adapter = Adapter()
    pack = extract(f, adapter, base=base)
    assert "merge" in adapter.calls
    kept = {n.text: n for n in pack.identity}
    assert kept["Works in finance"].superseded_by  # contradicted, kept, superseded
    assert "Works in AI" in kept
    assert pack.manifest.source_models == ["old-model", "fake-1"]
