"""Backtest runner tests on the engine tests' synthetic market (no Breeze login needed).

    .venv\\Scripts\\python -m pytest tests/test_paper_backtest.py -q
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from backend.paper import backtest as BT
from backend.paper import engine
from backend.paper.config import PaperConfig
from test_paper_engine import DAYS, FakeMarket, at_close, sessions

SCEN = {DAYS[5]: "dip_rebound", DAYS[7]: "dip_fall", DAYS[9]: "spike_fade"}


@pytest.mark.parametrize("day, weekday", [
    (dt.date(2024, 3, 4), 3),   # Thursday weeklies
    (dt.date(2025, 8, 27), 3),  # Wed: the last Thursday weekly (28 Aug) is still nearer than Tue 2 Sep
    (dt.date(2025, 8, 29), 1),  # Fri: no Thursday weekly left; the first Tuesday one
    (dt.date(2026, 6, 3), 1),
])
def test_expiry_weekday_follows_the_nse_calendar(day, weekday):
    assert BT.expiry_weekday_for(day) == weekday


def test_backtest_matches_the_paper_record():
    """Same sessions, same settings: the backtest and a caught-up paper record trade identically."""
    cfg = PaperConfig(catch_up_missed_days=True)
    md = FakeMarket(DAYS, SCEN)
    paper = engine.step(md, cfg, None, at_close(DAYS[4]))
    paper = engine.step(md, cfg, paper, at_close(DAYS[10]))
    bt = BT.run_backtest(FakeMarket(DAYS, SCEN), cfg, DAYS[4], DAYS[10])
    assert bt["trades"] == paper["trades"] and bt["equity"] == paper["equity"]
    assert len(bt["trades"]) >= 3 and bt["kind"] == "backtest" and bt["end"] == DAYS[10].isoformat()


def test_thursday_era_sessions_trade_the_thursday_weekly():
    days = sessions(dt.date(2025, 8, 4), 12)  # Mon 4 Aug 2025 ..
    md = FakeMarket(days, {days[6]: "dip_rebound"})
    trades = BT.run_backtest(md, PaperConfig(), days[4], days[-1])["trades"]
    assert trades and all(dt.date.fromisoformat(t["expiry"]).weekday() == 3 for t in trades)


def test_report_halves_add_up():
    ledger = BT.run_backtest(FakeMarket(DAYS, SCEN), PaperConfig(), DAYS[4], DAYS[10])
    rep = BT.report(ledger, split=DAYS[8])
    o, i, s = rep["overall"], rep["in_sample"], rep["out_of_sample"]
    assert o["net_pnl"] == pytest.approx(sum(t["pnl"] for t in ledger["trades"]), abs=0.01)
    assert o["trades"] == len(ledger["trades"]) and i["trades"] and s["trades"]
    assert i["trades"] + s["trades"] == o["trades"]
    assert i["sessions"] + s["sessions"] == o["sessions"] == 7
    assert i["return_pct"] + s["return_pct"] == pytest.approx(o["return_pct"], abs=0.02)
    assert s["from"] == DAYS[8].isoformat()
    assert sum(o["by_exit"].values()) == o["trades"] == sum(m["trades"] for m in rep["monthly"])
    assert o["win_rate_pct"] == pytest.approx(100 * sum(t["pnl"] > 0 for t in ledger["trades"]) / o["trades"], abs=0.1)
    assert rep["sessions_with_missed_signals"] == 0 and rep["sessions_without_data"] == 0


def test_missing_option_prices_are_counted():
    md = FakeMarket(DAYS, {DAYS[6]: "dip_rebound"})
    md.option_bars = lambda *a: pd.DataFrame(columns=["Open", "High", "Low", "Close"])
    rep = BT.report(BT.run_backtest(md, PaperConfig(), DAYS[4], DAYS[8]))
    assert rep["overall"]["trades"] == 0 and rep["sessions_with_missed_signals"] >= 1


class Counting:
    def __init__(self, md):
        self.md, self.calls = md, 0

    def __getattr__(self, name):
        fn = getattr(self.md, name)

        def wrapped(*a):
            self.calls += 1
            return fn(*a)
        return wrapped


def test_cache_serves_repeat_runs_from_disk(tmp_path):
    raw = Counting(FakeMarket(DAYS, SCEN))
    md = BT.CachedMarket(raw, root=tmp_path)
    first = BT.run_backtest(md, PaperConfig(), DAYS[4], DAYS[10])
    option_calls = raw.calls
    raw.calls = 0
    second = BT.run_backtest(md, PaperConfig(), DAYS[4], DAYS[10])
    assert second["trades"] == first["trades"]
    assert raw.calls < option_calls  # only the index is fetched again
    assert raw.calls == len(list(BT._spans(DAYS[4] - dt.timedelta(days=10), DAYS[10], 365))) + \
        len(list(BT._spans(DAYS[4] - dt.timedelta(days=engine.WARMUP_DAYS), DAYS[10], 900 // 77)))


def test_cache_skips_empty_answers(tmp_path):
    md = BT.CachedMarket(FakeMarket(DAYS, dead_expiries={dt.date(2026, 6, 9)}), root=tmp_path)
    assert md.option_bars(dt.date(2026, 6, 9), 22000, "call", DAYS[5]).empty
    assert not list(tmp_path.rglob("*.csv"))


def test_throttle_counts_calls():
    class Client:
        def get_historical_data_v2(self, **kw):
            return {"Success": []}

        def other(self):
            return "passed through"
    c = BT.ThrottledClient(Client(), per_minute=60_000)
    c.get_historical_data_v2(interval="1day")
    c.get_historical_data_v2(interval="1day")
    assert c.calls == 2 and c.other() == "passed through"


def test_sweep_ranks_in_sample_and_reports_out_of_sample():
    rows = BT.sweep(FakeMarket(DAYS, SCEN), PaperConfig(), DAYS[4], DAYS[10],
                    {"target_pct": [10, 30], "stop_pct": [20]}, split=DAYS[8])
    assert len(rows) == 2 and {r["params"]["target_pct"] for r in rows} == {10, 30}
    assert rows[0]["in_sample"]["net_pnl"] >= rows[1]["in_sample"]["net_pnl"]
    assert set(rows[0]) == {"params", "in_sample", "out_of_sample"}


def test_sweep_rejects_unknown_settings():
    with pytest.raises(KeyError):
        BT.sweep(FakeMarket(DAYS), PaperConfig(), DAYS[4], DAYS[6], {"nope": [1]})


def test_execute_result_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(BT, "RESULTS", tmp_path)
    result = BT.execute(FakeMarket(DAYS, SCEN), PaperConfig(), DAYS[4], DAYS[10], split=DAYS[8])
    BT.save_result("t1", result)
    assert BT.load_result("t1")["report"] == result["report"]
    assert BT.list_results()[0]["name"] == "t1"
    assert BT.load_result("../ledger") is None
