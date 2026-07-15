from pathlib import Path

import pytest
from typer.testing import CliRunner

from cortical_transfer import store
from cortical_transfer.cli import app
from cortical_transfer.integrity import load_pack
from cortical_transfer.schema import SemanticNode

runner = CliRunner()


@pytest.fixture(autouse=True)
def ct_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def test_init_inspect_verify() -> None:
    assert runner.invoke(app, ["init"]).exit_code == 0
    assert runner.invoke(app, ["init"]).exit_code != 0  # already exists
    r = runner.invoke(app, ["inspect"])
    assert r.exit_code == 0 and "identity (0)" in r.output
    assert runner.invoke(app, ["verify"]).exit_code == 0


def test_diff_log_checkout() -> None:
    store.init_profile()
    pack = load_pack(store.profile_path())
    pack.identity.append(SemanticNode(text="uses uv", salience=0.8))
    pack.episodes.append(SemanticNode(text="tried pip first"))
    store.commit_pack(pack, "default", "feat: add facts")

    lines = store.diff("default", "HEAD~1", "HEAD")
    assert any("+ [identity] uses uv" in line for line in lines)
    assert any("+ [episodes] tried pip first" in line for line in lines)

    # supersede + text change show up
    new = SemanticNode(text="uses uv exclusively")
    pack.identity[0].superseded_by = new.id
    pack.identity.append(new)
    store.commit_pack(pack, "default", "fix: supersede")
    lines = store.diff("default", "HEAD~1", "HEAD")
    assert any("superseded: uses uv" in line for line in lines)

    assert len(store.log()) == 3

    store.checkout("default", "HEAD~2")  # back to empty state, as new commit
    restored = load_pack(store.profile_path())
    assert restored.identity == [] and len(store.log()) == 4


def test_verify_fails_on_tamper() -> None:
    store.init_profile()
    p = store.profile_path() / "identity.json"
    p.write_text('[{"id":"01BX5ZZKBKACTAV9WEVGEMMVRZ","text":"injected"}]')
    assert runner.invoke(app, ["verify"]).exit_code == 1
