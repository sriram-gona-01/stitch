import json
import subprocess
import sys
from pathlib import Path

from lightwork import cli, offload

GATE = Path(__file__).parents[1] / "src" / "lightwork" / "hooks" / "verify_gate.py"


def gate_repo(tmp_path, **verify):
    target = tmp_path / "src" / "lightwork" / "hooks" / "verify_gate.py"
    target.parent.mkdir(parents=True)
    target.write_text(GATE.read_text())
    (tmp_path / ".lightwork").mkdir()
    (tmp_path / ".lightwork" / "state.json").write_text(json.dumps({"config": {"verify": verify}}))
    return target


def run_gate(hook, payload="{}"):
    return subprocess.run([sys.executable, "-IS", str(hook)], input=payload, text=True, capture_output=True)


def test_failure_blocks_with_only_first_lines(tmp_path):
    hook = gate_repo(tmp_path, fast_cmd="printf 'one\\ntwo\\nthree\\n'; exit 3", max_failure_lines=2)
    result = run_gate(hook)
    decision = json.loads(result.stdout)
    assert result.returncode == 0 and decision["decision"] == "block"
    assert "one" in decision["reason"] and "two" in decision["reason"] and "three" not in decision["reason"]


def test_success_lets_claude_stop(tmp_path):
    assert run_gate(gate_repo(tmp_path, fast_cmd="true")).stdout == ""


def test_stop_hook_active_never_blocks_again(tmp_path):
    hook = gate_repo(tmp_path, fast_cmd="false")
    assert run_gate(hook, json.dumps({"stop_hook_active": True})).stdout == ""


def test_timeout_fails_open(tmp_path):
    hook = gate_repo(tmp_path, fast_cmd="sleep 5", timeout_seconds=0.1)
    result = run_gate(hook)
    assert (result.returncode, result.stdout) == (0, "")


def test_missing_state_and_bad_input_fail_open(tmp_path):
    hook = gate_repo(tmp_path, fast_cmd="false")
    assert run_gate(hook, "{bad").stdout == ""
    (tmp_path / ".lightwork" / "state.json").unlink()
    assert run_gate(hook).stdout == ""


def test_summary_of_long_log_fits_and_keeps_failures(tmp_path):
    lines = [f"ok {i}" for i in range(5000)]
    lines[2500] = "FAILED tests/test_x.py::test_y"
    summary = offload.summarize("\n".join(lines), 1, tmp_path / "x.log")
    out = summary.splitlines()
    assert len(out) <= offload.MAX_LINES
    assert out[0].startswith("exit code: 1")
    assert "FAILED tests/test_x.py::test_y" in out
    assert out[-1].endswith("x.log") and "ok 4999" in out


def test_many_failures_still_within_limit(tmp_path):
    output = "\n".join(f"error {i}" for i in range(1000))
    assert len(offload.summarize(output, 1, tmp_path / "x", max_failures=500).splitlines()) <= offload.MAX_LINES


def test_short_output_is_shown_whole(tmp_path):
    assert "a\nb" in offload.summarize("a\nb\n", 0, tmp_path / "x")


def test_long_lines_are_clipped(tmp_path):
    assert max(len(l) for l in offload.summarize("x" * 5000, 0, tmp_path / "x").splitlines()[:2]) < 300


def test_run_saves_full_output_and_passes_exit_code(tmp_path, monkeypatch, capsys):
    (tmp_path / "lightwork.yaml").write_text("{}\n")
    monkeypatch.chdir(tmp_path)
    code = cli.main(["run", "--", sys.executable, "-c", "print('hi\\n'*100); raise SystemExit(4)"])
    assert code == 4
    logs = list((tmp_path / ".lightwork" / "offload").glob("*.log"))
    assert len(logs) == 1 and logs[0].read_text().count("hi") == 100
    assert str(logs[0]) in capsys.readouterr().out


def test_missing_command_is_reported(tmp_path):
    code, summary = offload.run_command(["definitely-not-a-command-xyz"], tmp_path)
    assert code == 127 and "Could not run" in summary
