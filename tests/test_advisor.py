import json

import pytest

from lightwork import advisor
from lightwork.hooks.advise_hook import advisory, last_context_tokens
from lightwork.pricing import MissingPriceError, Price
from lightwork.transcripts import Request

# Round test prices, not real ones: $ per million tokens.
BIG = Price(input=10, output=20, cache_write=10, cache_read=1)
SMALL = Price(input=1, output=2, cache_write=1, cache_read=0.1)


def test_stay_hand_checked():
    # 10 × (100,000 × $1 + 1,000 × $20) / 1M = 10 × 0.12 = $1.20
    assert advisor.stay_cost(100_000, 1_000, 10, BIG) == pytest.approx(1.20)


def test_switch_hand_checked():
    # Write 100,000 × $1 = 0.10; 9 reads × 100,000 × $0.1 = 0.09; output 10 × 1,000 × $2 = 0.02
    assert advisor.switch_cost(100_000, 1_000, 10, SMALL) == pytest.approx(0.21)


def test_delegate_hand_checked():
    # Main: 500 × $20 = 0.01; read 100,000 × $1 = 0.10; summary 1,000 × $10 = 0.01 → 0.12
    # Sub: write 5,000 × $1 = 0.005; 9 × 5,000 × $0.1 = 0.0045; 10 × 1,000 × $2 = 0.02 → 0.0295
    cost = advisor.delegate_cost(100_000, 500, 1_000, 5_000, 1_000, 10, BIG, SMALL)
    assert cost == pytest.approx(0.1495)


def test_restart_hand_checked():
    # Write handoff: 100,000 × $1 = 0.10 + 2,000 × $20 = 0.04 → 0.14
    # Continue: 2,000 × $10 = 0.02; 9 × 2,000 × $1 = 0.018; 10 × 1,000 × $20 = 0.20 → 0.238
    assert advisor.restart_cost(100_000, 2_000, 1_000, 10, BIG) == pytest.approx(0.378)


def test_break_even_turns_hand_checked():
    # Restart: 0.14 + (0.02 + 0.002(n-1) + 0.02n). Stay: 0.12n. Equal when 0.158 = 0.098n, n ≈ 1.6.
    option = lambda n: advisor.restart_cost(100_000, 2_000, 1_000, n, BIG)
    stay = lambda n: advisor.stay_cost(100_000, 1_000, n, BIG)
    assert advisor.break_even_turns(option, stay) == 2
    assert advisor.break_even_turns(lambda n: 1e9, stay, limit=5) is None


def main_request(i=0, context=100_000, output=1_000, feature="F", phase="build", agent="main", agent_id="", model="big", session="s"):
    return Request(
        f"k{agent}{i}", session, model, f"2026-01-01T00:00:{i:02d}Z", agent, agent_id,
        0, output, 0, context, feature, phase, "route",
    )


PRICES = {"big": BIG, "small": SMALL}


def test_advise_recommends_delegate_with_numbers():
    requests = [main_request(), main_request(1, context=5_000, output=1_000, agent="scout", agent_id="a", model="small")]
    text = advisor.advise(requests, PRICES, {"min_saving": 0.1}, "F", "build", remaining_turns=10)
    assert text.startswith("Recommendation: delegate to scout")
    assert "stay: $1.2000" in text and "delegate to scout: $" in text


def test_advise_stays_when_savings_are_small():
    requests = [main_request(context=1_000, output=10)]
    text = advisor.advise(requests, {"big": BIG}, {"min_saving": 0.1}, "F", "build", remaining_turns=1)
    assert text.startswith("Recommendation: stay")
    assert "no delegation estimate" in text


def test_advise_never_recommends_switching():
    text = advisor.advise([main_request()], PRICES, {}, "F", "build", remaining_turns=50)
    assert "switching main to small" in text
    assert "switch" not in text.splitlines()[0].lower()


def test_advise_refuses_without_data_or_price():
    with pytest.raises(advisor.NoDataError):
        advisor.advise([], PRICES, {})
    with pytest.raises(MissingPriceError):
        advisor.advise([main_request()], {}, {})


def test_remaining_turns_come_from_past_runs():
    past = [main_request(i, feature="OLD", session="old") for i in range(6)]
    text = advisor.advise([*past, main_request(10)], PRICES, {}, "F", "build")
    assert "Remaining turns assumed: 5 (from 1 past run(s) averaging 6 turns)" in text


def test_subagent_stats_measure_first_context_and_last_output():
    runs = [
        main_request(1, context=1000, output=10, agent="scout", agent_id="a", model="small"),
        main_request(2, context=2000, output=30, agent="scout", agent_id="a", model="small"),
    ]
    stat = advisor.subagent_stats(runs)[0]
    assert (stat.context, stat.output, stat.summary, stat.turns) == (1000, 20, 30, 2)


def write_transcript(path, cache_read):
    event = {"type": "assistant", "message": {"usage": {"input_tokens": 1, "cache_read_input_tokens": cache_read}}}
    path.write_text('partial line\n' + json.dumps(event) + "\n" + json.dumps({"type": "user"}) + "\n")


def test_hook_silent_below_threshold_and_in_baseline(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, 200)
    assert last_context_tokens(transcript) == 201
    state = {"arm": "route", "config": {"advisor": {"context_warn_tokens": 1000}}}
    assert advisory({"transcript_path": str(transcript)}, state) is None
    write_transcript(transcript, 5000)
    assert advisory({"transcript_path": str(transcript)}, {**state, "arm": "baseline"}) is None


def test_hook_adds_one_line_past_threshold(tmp_path):
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, 5000)
    state = {"arm": "route", "config": {"advisor": {"context_warn_tokens": 1000}}}
    context = advisory({"transcript_path": str(transcript)}, state)["hookSpecificOutput"]["additionalContext"]
    assert "5,001" in context and "\n" not in context
