import json
from pathlib import Path

import pytest
from git import GitCommandError, Repo

from cortical_transfer import store
from cortical_transfer.integrity import load_pack
from cortical_transfer.redact import redact, remove_node
from cortical_transfer.schema import MemPack, SemanticNode


@pytest.fixture(autouse=True)
def ct_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_remove_node_nulls_references() -> None:
    victim = SemanticNode(text="secret")
    child = SemanticNode(text="child", parent_id=victim.id)
    old = SemanticNode(text="old", superseded_by=victim.id)
    pack = MemPack(identity=[old], episodes=[victim, child])
    refs = remove_node(pack, victim.id)
    assert refs == []
    assert victim.id not in [n.id for n in pack.all_nodes()]
    assert child.parent_id is None and old.superseded_by is None
    with pytest.raises(KeyError):
        remove_node(pack, victim.id)


def test_redact_erases_content_and_history() -> None:
    store.init_profile()
    pack = load_pack(store.profile_path())
    victim = SemanticNode(text="SECRET-PHRASE-42", source_refs=["c1:0"])
    pack.identity.append(victim)
    pack.episodes.append(SemanticNode(text="harmless memory"))
    raw = store.profile_path() / "raw"
    raw.mkdir()
    (raw / "c1.jsonl").write_text(
        '{"turn_id": "c1:0", "content": "the secret phrase is 42"}\n'
        '{"turn_id": "c1:1", "content": "unrelated"}\n'
    )
    store.commit_pack(pack, "default", "seed with secret")

    redact("default", victim.id)

    after = load_pack(store.profile_path())
    assert "SECRET-PHRASE-42" not in json.dumps([n.text for n in after.all_nodes()])
    assert after.episodes[0].text == "harmless memory"  # everything else survives
    raw_left = (raw / "c1.jsonl").read_text()
    assert "secret phrase" not in raw_left and "unrelated" in raw_left

    repo = Repo(store.profile_path())
    assert len(list(repo.iter_commits())) == 1  # squashed baseline only
    with pytest.raises(GitCommandError):  # no match in the only remaining commit
        repo.git.grep("SECRET-PHRASE-42", "HEAD")
    assert repo.git.fsck("--unreachable").strip() == ""  # old objects pruned


class HashEmbed:
    """Deterministic toy embedding — tests Chroma plumbing without model downloads."""

    def __call__(self, input: list[str]) -> list[list[float]]:
        out = []
        for text in input:
            v = [0.0] * 32
            for word in text.lower().split():
                v[hash(word) % 32] += 1.0
            out.append(v)
        return out

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self(input)

    def name(self) -> str:
        return "hash-embed-test"


def test_rag_index_and_search(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    from cortical_transfer.rag import index_raw, search_raw

    pack_dir = tmp_path / "pack"
    (pack_dir / "raw").mkdir(parents=True)
    (pack_dir / "raw" / "c1.jsonl").write_text(
        '{"turn_id": "1", "content": "we discussed flutter caregiving app icons"}\n'
        '{"turn_id": "2", "content": "ollama moe offload prefill speedup"}\n'
    )
    ef = HashEmbed()
    assert index_raw(pack_dir, embedding_function=ef) == 2
    hits = search_raw(pack_dir, "flutter caregiving app icons", k=1, embedding_function=ef)
    assert hits == ["we discussed flutter caregiving app icons"]


def test_rag_empty_index(tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    from cortical_transfer.rag import search_raw

    assert search_raw(tmp_path, "anything", embedding_function=HashEmbed()) == []
