from lightwork.pricing import Price
from lightwork.report import build_report, parse_guardrails
from lightwork.transcripts import Request

PRICE = Price(input=1, output=2, cache_write=1, cache_read=0.1)


def req(key, session, arm, agent="main", feature="F1", read=900, inp=100, out=10):
    return Request(key, session, "m", "2026-01-01T00:00:00Z", agent, "", inp, out, 0, read, feature, "build", arm)


def row(text, arm):
    return next(line for line in text.splitlines() if f"| {arm} |" in line)


def test_guardrails_parse_and_skip_malformed():
    text = (
        "guardrail: feature=F1 arm=route run=1 first_run_pass=yes corrections=2 claude=2.1.309\n"
        "- guardrail: feature=F1 arm=route run=2 first_run_pass=no corrections=0\n"
        "guardrail: feature=F1 corrections=many\n"
        "unrelated line\n"
    )
    parsed = parse_guardrails(text)
    assert [(g.first_run_pass, g.corrections) for g in parsed] == [(True, 2), (False, 0)]


def test_report_compares_arms_per_run():
    requests = [req("a", "s1", "baseline"), req("b", "s2", "baseline"), req("c", "s3", "route", agent="scout")]
    guardrails = parse_guardrails("guardrail: feature=F1 arm=route run=1 first_run_pass=yes corrections=1\n")
    text = build_report(requests, {"m": PRICE}, guardrails, ["F1"], ["baseline", "route"])
    # Each request: (100×1 + 10×2 + 900×0.1) / 1M = 0.00021; tokens = 100 + 900 + 10.
    assert "| F1 | baseline | 2 | 0.0002 | 1,010 | 90.0% | main: 2,020 | not recorded | not recorded |" in text
    assert row(text, "route").endswith("| scout: 1,010 | 1/1 | 1.0 |")


def test_report_without_prices_or_data_says_so():
    text = build_report([req("a", "s1", "route")], {}, [], ["F1"], ["route", "baseline"])
    assert "n/a (price missing)" in row(text, "route")
    assert "| F1 | baseline | 0 | no data |" in text
