import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lightwork import state
from lightwork.hooks.log_event import build_line, output_chars
from lightwork.tagging import agent_names, read_events, tag_requests
from lightwork.transcripts import Request

HOOK = Path(__file__).parents[1] / "src" / "lightwork" / "hooks" / "log_event.py"


def req(ts):
    return Request("k" + ts, "s", "m", ts)


def marker(ts, feature, phase, arm="route"):
    return {"ts": ts, "event": state.MARKER, "feature": feature, "phase": phase, "arm": arm}


def test_requests_take_latest_marker_at_or_before_their_time():
    events = [
        marker("2026-01-01T00:00:10.000Z", "F1", "plan"),
        marker("2026-01-01T00:00:20.000Z", "F1", "build"),
        marker("2026-01-01T00:00:30.000Z", None, None),
    ]
    tagged = tag_requests(
        [req(t) for t in ("2026-01-01T00:00:05Z", "2026-01-01T00:00:10Z", "2026-01-01T00:00:25Z", "2026-01-01T00:00:35Z")],
        events,
    )
    assert [(r.feature, r.phase) for r in tagged] == [("", ""), ("F1", "plan"), ("F1", "build"), ("", "")]
    assert tagged[0].arm == "baseline" and tagged[1].arm == "route"


def test_bad_timestamp_stays_untagged():
    assert tag_requests([req("not a time")], [marker("2026-01-01T00:00:00Z", "F", "plan")])[0].feature == ""


def test_feature_lifecycle_writes_state_and_markers(tmp_path):
    state.feature_start(tmp_path, "F1")
    state.feature_phase(tmp_path, "build")
    assert state.load_state(tmp_path)["phase"] == "build"
    state.feature_end(tmp_path)
    assert state.load_state(tmp_path)["feature"] is None
    events = read_events(state.events_path(tmp_path))
    assert [e["phase"] for e in events] == ["plan", "build", None]


def test_phase_without_feature_is_refused(tmp_path):
    with pytest.raises(ValueError):
        state.feature_phase(tmp_path, "build")


def test_agent_names_from_events():
    assert agent_names([{"agent_id": "a", "agent_type": "scout"}, {"agent_id": "b", "agent_type": ""}, {}]) == {"a": "scout"}


@pytest.mark.parametrize(
    "response,expected",
    [("abc", 3), ({"stdout": "ab", "stderr": "c", "interrupted": False}, 3), ({"x": 1}, len('{"x": 1}'))],
)
def test_output_chars(response, expected):
    assert output_chars(response) == expected


def test_log_line_has_sizes_not_content():
    line = build_line(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "s",
            "tool_name": "Bash",
            "tool_input": {"command": "SECRET"},
            "tool_response": {"stdout": "SECRET", "stderr": ""},
        },
        {"feature": "F", "phase": "test", "arm": "route"},
        "now",
    )
    assert line["output_chars"] == 6 and line["tool"] == "Bash" and line["arm"] == "route"
    assert "SECRET" not in json.dumps(line)


def _copy_hook(tmp_path, source=HOOK):
    target = tmp_path / "src" / "lightwork" / "hooks" / source.name
    target.parent.mkdir(parents=True)
    target.write_text(source.read_text())
    return target


def test_hook_appends_a_line_quickly(tmp_path):
    hook = _copy_hook(tmp_path)
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-IS", str(hook)],
        input=json.dumps({"hook_event_name": "Stop", "session_id": "s"}),
        text=True,
        capture_output=True,
    )
    elapsed = time.perf_counter() - start
    assert result.returncode == 0 and result.stdout == ""
    assert elapsed < 0.2
    assert json.loads((tmp_path / ".lightwork" / "events.jsonl").read_text())["event"] == "Stop"


def test_hook_fails_open_on_garbage(tmp_path):
    hook = _copy_hook(tmp_path)
    result = subprocess.run([sys.executable, "-IS", str(hook)], input="{not json", text=True, capture_output=True)
    assert result.returncode == 0 and result.stdout == "" and result.stderr == ""


def test_usage_by_phase_end_to_end(tmp_path, monkeypatch, capsys):
    from lightwork import cli, usage

    (tmp_path / "lightwork.yaml").write_text("paths: {aliases: []}\n")
    monkeypatch.chdir(tmp_path)
    usage.write_snapshot([Request("a", "s", "m", "2026-01-01T00:00:15Z", input_tokens=7)], tmp_path / ".lightwork" / "snapshots")
    state.events_path(tmp_path).write_text(json.dumps(marker("2026-01-01T00:00:10Z", "F1", "build")) + "\n")
    assert cli.main(["usage", "--feature", "F1", "--by", "phase"]) == 0
    out = capsys.readouterr().out
    assert "build" in out and "7" in out
