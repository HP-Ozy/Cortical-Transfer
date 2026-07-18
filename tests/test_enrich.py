from pathlib import Path

import pytest

from cortical_transfer import store
from cortical_transfer.inject import enrich, merge_packs
from cortical_transfer.schema import MemPack, SemanticNode


@pytest.fixture()
def two_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CT_HOME", str(tmp_path))
    for name, fact in [("claude", "works on AI agents"), ("qwen", "prefers Italian")]:
        store.init_profile(name)
        pack = MemPack(identity=[SemanticNode(text=fact), SemanticNode(text="shared fact")])
        store.commit_pack(pack, name, "test")


def test_enrich_merges_all_profiles(two_profiles: None) -> None:
    out = enrich("Qual e il piano?")
    assert "works on AI agents" in out and "prefers Italian" in out
    assert out.endswith("Qual e il piano?")
    assert out.count("shared fact") == 1  # deduped across models


def test_enrich_no_profiles_returns_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CT_HOME", str(tmp_path / "empty"))
    assert enrich("ciao") == "ciao"


def test_merge_keeps_all_styles() -> None:
    a = MemPack(style="Short.")
    b = MemPack(style="Italian.")
    assert merge_packs([a, b]).style == "Short.\nItalian."
