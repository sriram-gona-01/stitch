from pathlib import Path

from lightwork.transcripts import encode_project_path, load_requests, parse_file, parse_session, project_dirs

FIXTURES = Path(__file__).parent / "fixtures" / "projects"
SESSION = FIXTURES / "sess-1.jsonl"


def by_key():
    return {r.key: r for r in parse_session(SESSION)}


def test_encode_replaces_every_non_alphanumeric():
    assert encode_project_path("/Users/a b/AI_Eng.x") == "-Users-a-b-AI-Eng-x"


def test_project_dirs_finds_current_and_alias(tmp_path):
    (tmp_path / "-repo-new").mkdir()
    (tmp_path / "-repo-old").mkdir()
    found = project_dirs(Path("/repo/new"), ["/repo/old", "/repo/gone"], tmp_path)
    assert [p.name for p in found] == ["-repo-new", "-repo-old"]


def test_duplicate_lines_count_once_and_keep_highest_output():
    requests = {r.key: r for r in parse_file(SESSION)}
    assert requests["msg-1|req-1"].output_tokens == 20
    assert sum(1 for k in requests if k == "msg-1|req-1") == 1


def test_missing_usage_fields_default_to_zero():
    request = by_key()["msg-2|req-2"]
    assert (request.cache_write_tokens, request.cache_read_tokens) == (0, 0)


def test_skips_synthetic_no_usage_other_types_and_bad_lines():
    keys = set(by_key())
    assert not any("msg-9" in k or "no-usage" in k for k in keys)
    assert len(keys) == 5


def test_main_and_sidechain_attribution():
    requests = by_key()
    assert requests["msg-1|req-1"].agent == "main"
    assert requests["msg-3|req-3"].agent == "unknown"
    assert requests["msg-3|req-3"].agent_id == "inline"


def test_subagent_file_supplies_name_and_wins_over_main_file():
    request = by_key()["msg-4|req-4"]
    assert (request.agent, request.agent_id) == ("scout", "abc")
    assert by_key()["msg-5|req-5"].agent == "scout"


def test_agent_names_map_fills_sidechain_turns():
    requests = {r.key: r for r in parse_session(SESSION, {"inline": "reviewer"})}
    assert requests["msg-3|req-3"].agent == "reviewer"


def test_load_requests_is_sorted_by_time():
    timestamps = [r.timestamp for r in load_requests([FIXTURES])]
    assert timestamps == sorted(timestamps) and len(timestamps) == 5
