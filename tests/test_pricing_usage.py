import pytest

from lightwork.pricing import MissingPriceError, Price, load_prices, request_cost, total_cost
from lightwork.transcripts import Request
from lightwork.usage import (
    aggregate,
    cache_hit_ratio,
    format_table,
    load_snapshots,
    merge_with_snapshots,
    write_csv,
    write_snapshot,
)

PRICE = Price(input=3.0, output=15.0, cache_write=4.0, cache_read=0.5)


def req(key="k", model="m", agent="main", i=0, o=0, w=0, r=0, session="s"):
    return Request(key, session, model, "2026-01-01T00:00:00Z", agent, "", i, o, w, r)


def test_cost_prices_each_field_separately():
    # 1M at each price: 3 + 15 + 4 + 0.5
    million = 1_000_000
    assert request_cost(req(i=million, o=million, w=million, r=million), PRICE) == pytest.approx(22.5)
    # Hand-checked: (1000*3 + 2000*15 + 4000*4 + 8000*0.5) / 1e6 = 53000 / 1e6
    assert request_cost(req(i=1000, o=2000, w=4000, r=8000), PRICE) == pytest.approx(0.053)


def test_total_cost_refuses_missing_model():
    with pytest.raises(MissingPriceError) as error:
        total_cost([req(model="m"), req(model="other")], {"m": PRICE})
    assert error.value.models == ["other"]


def test_load_prices_ignores_incomplete_entries(tmp_path):
    path = tmp_path / "pricing.yaml"
    path.write_text(
        "models:\n"
        "  full: {input: 1, output: 2, cache_write: 3, cache_read: 0.5}\n"
        "  blank: {input: null, output: 2, cache_write: 3, cache_read: 0.5}\n"
    )
    assert set(load_prices(path)) == {"full"}
    assert load_prices(tmp_path / "absent.yaml") == {}


def test_cache_hit_ratio():
    assert cache_hit_ratio(input_tokens=10, cache_write=30, cache_read=60) == pytest.approx(0.6)
    assert cache_hit_ratio(0, 0, 0) == 0.0


def test_aggregate_groups_and_sums():
    rows = aggregate(
        [req("a", agent="main", i=1, r=9), req("b", agent="scout", i=5), req("c", agent="main", o=2)],
        {"m": PRICE},
        lambda r: r.agent,
    )
    assert [r.group for r in rows] == ["main", "scout"]
    assert (rows[0].requests, rows[0].input_tokens, rows[0].output_tokens) == (2, 1, 2)
    assert rows[0].cache_hit_ratio == pytest.approx(0.9)


def test_missing_price_gives_no_cost_but_keeps_tokens():
    row = aggregate([req(i=5)], {})[0]
    assert row.cost_usd is None and row.input_tokens == 5
    assert "n/a" in format_table([row])


def test_csv_written(tmp_path):
    path = tmp_path / "out" / "u.csv"
    write_csv(aggregate([req(i=5)], {"m": PRICE}), path)
    assert path.read_text().splitlines()[0].startswith("group,requests")


def test_snapshot_round_trip_survives_transcript_cleanup(tmp_path):
    write_snapshot([req("a", i=1), req("b", i=2)], tmp_path)
    write_snapshot([req("a", i=10)], tmp_path)  # later snapshot updates, keeps the rest
    saved = {r.key: r.input_tokens for r in load_snapshots(tmp_path)}
    assert saved == {"a": 10, "b": 2}
    merged = merge_with_snapshots([req("b", i=20)], load_snapshots(tmp_path))
    assert {r.key: r.input_tokens for r in merged} == {"a": 10, "b": 20}


def test_snapshot_rows_hold_no_content(tmp_path):
    write_snapshot([req("a", i=1)], tmp_path)
    assert "content" not in (tmp_path / "s.jsonl").read_text()
