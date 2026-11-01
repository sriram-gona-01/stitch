import json
import shutil
from pathlib import Path

import pytest

from lightwork import arms, state

REPO = Path(__file__).parents[1]


@pytest.fixture
def repo(tmp_path):
    shutil.copytree(REPO / "harness", tmp_path / "harness")
    shutil.copyfile(REPO / "CLAUDE.md", tmp_path / "CLAUDE.md")
    shutil.copyfile(REPO / "lightwork.yaml", tmp_path / "lightwork.yaml")
    return tmp_path


def agents(repo):
    return sorted(p.stem for p in (repo / ".claude" / "agents").glob("*.md"))


def settings(repo):
    return json.loads((repo / ".claude" / "settings.json").read_text())


def test_headroom_arm_is_blocked_until_tested(repo):
    with pytest.raises(arms.ArmError, match="blocked"):
        arms.apply_arm(repo, "headroom")


def test_arm_inheritance():
    loaded = arms.load_arms(REPO)
    assert loaded["baseline"].agents == () and loaded["baseline"].hooks == ("log",)
    assert set(loaded["verify"].agents) == {"test-runner", "test-writer"}
    assert set(loaded["route"].agents) == {"test-runner", "test-writer", "scout", "implementer", "reviewer"}
    assert loaded["offload"].fragments == ("routing", "offload")


def test_baseline_is_clean_after_route(repo):
    before = (repo / "CLAUDE.md").read_text()
    arms.apply_arm(repo, "route")
    assert len(agents(repo)) == 5
    assert "@harness/claude-md/routing.md" in (repo / "CLAUDE.md").read_text()
    assert "Stop" in settings(repo)["hooks"]
    arms.apply_arm(repo, "baseline")
    assert agents(repo) == []
    assert (repo / "CLAUDE.md").read_text() == before
    assert "Routing" not in before
    assert not any("verify_gate" in json.dumps(g) for g in settings(repo)["hooks"]["Stop"])


def test_switching_back_restores_identical_files(repo):
    arms.apply_arm(repo, "route")
    first = ((repo / "CLAUDE.md").read_text(), (repo / ".claude" / "settings.json").read_text())
    arms.apply_arm(repo, "baseline")
    arms.apply_arm(repo, "route")
    assert ((repo / "CLAUDE.md").read_text(), (repo / ".claude" / "settings.json").read_text()) == first


def test_baseline_registers_logging_only(repo):
    arms.apply_arm(repo, "baseline")
    commands = json.dumps(settings(repo))
    assert "log_event.py" in commands and "verify_gate" not in commands and "advise_hook" not in commands


def test_foreign_settings_and_hooks_are_kept(repo):
    path = repo / ".claude" / "settings.json"
    path.parent.mkdir()
    mine = {"hooks": [{"type": "command", "command": "mine.sh"}]}
    path.write_text(json.dumps({"model": "x", "hooks": {"Stop": [mine]}}))
    arms.apply_arm(repo, "baseline")
    assert settings(repo)["model"] == "x"
    assert mine in settings(repo)["hooks"]["Stop"]


def test_hook_commands_stay_fail_open():
    assert arms.hook_command("x.py").endswith("|| true")


def test_arm_recorded_in_state_with_hook_config(repo):
    arms.apply_arm(repo, "verify")
    current = state.load_state(repo)
    assert current["arm"] == "verify" and "fast_cmd" in current["config"]["verify"]
    assert arms.active_arm(repo) == "verify"


def test_unknown_blocked_and_missing_marker_errors(repo):
    with pytest.raises(arms.ArmError):
        arms.apply_arm(repo, "nope")
    (repo / "harness" / "arms.yaml").write_text("arms: {x: {blocked: no login support}}\n")
    with pytest.raises(arms.ArmError, match="no login support"):
        arms.apply_arm(repo, "x")
    (repo / "harness" / "arms.yaml").write_text("arms: {x: {}}\n")
    (repo / "CLAUDE.md").write_text("no block")
    with pytest.raises(arms.ArmError):
        arms.apply_arm(repo, "x")


def test_advisor_hook_only_when_enabled_and_never_in_baseline(repo):
    path = repo / "lightwork.yaml"
    path.write_text(path.read_text().replace("hook_enabled: false", "hook_enabled: true"))
    arms.apply_arm(repo, "baseline")
    assert "advise_hook" not in json.dumps(settings(repo))
    arms.apply_arm(repo, "route")
    assert "advise_hook" in json.dumps(settings(repo))
