"""Intraday paper engine tests against a scripted synthetic market (no Breeze login needed).

    .venv\\Scripts\\python -m pytest tests/test_paper_engine.py -q
"""
from __future__ import annotations

import datetime as dt
import math

import pandas as pd
import pytest

from backend.paper import costs, engine
from backend.paper.config import PaperConfig
from backend.paper.engine import IST

OPEN = dt.time(9, 15)
MINUTES = 375  # 09:15 .. 15:29


def sessions(start: dt.date, n: int) -> list[dt.date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def path(kind: str, base: float = 22000.0) -> list[float]:
    """Nifty minute by minute for a scripted session."""
    p = []
    for m in range(MINUTES + 1):
        x = base + 15 * math.sin(2 * math.pi * m / 40)
        if kind != "flat" and m >= 45:
            sign = -1 if kind.startswith("dip") else 1
            k = min(m, 60) - 45  # a 15-minute slide (or spike) from 10:00: RSI crosses 20 at its end
            x = base + sign * 8 * k
            if m > 60:
                after = m - 60
                if kind in ("dip_rebound", "spike_fade"):
                    x += -sign * 12 * min(after, 60)
                elif kind == "dip_fall":
                    x += sign * 6 * after
        p.append(x)
    return p


class FakeMarket:
    def __init__(self, days, scenarios=None, dead_expiries=(), wide_bar_at=None, wide_first="stop", seconds=True,
                 gap_at=None):
        self.days = days
        self.scen = {d: (scenarios or {}).get(d, "flat") for d in days}
        self.paths = {d: path(self.scen[d]) for d in days}
        self.dead = set(dead_expiries)
        self.wide_bar_at = wide_bar_at  # (day, minute) where one option bar spans both target and stop
        self.wide_first = wide_first  # which level that minute's seconds reach first
        self.gap_at = gap_at  # (day, minute): the price gaps from above the stop to far below it
        if not seconds:
            self.option_seconds = None  # a data source without 1-second history

    def _t(self, d, m):
        return dt.datetime.combine(d, OPEN) + dt.timedelta(minutes=m)

    def index_daily(self, start, end):
        rows = {d: self.paths[d] for d in self.days if start <= d <= end}
        return pd.DataFrame({"Open": [p[0] for p in rows.values()], "High": [max(p) for p in rows.values()],
                             "Low": [min(p) for p in rows.values()], "Close": [p[-1] for p in rows.values()]},
                            index=list(rows))

    def index_bars(self, start, end, interval):
        n = int(interval.replace("minute", ""))
        recs = []
        for d in self.days:
            if not start <= d <= end:
                continue
            p = self.paths[d]
            for m in range(0, MINUTES, n):
                seg = p[m:m + n + 1]
                recs.append((self._t(d, m), seg[0], max(seg), min(seg), seg[-1]))
        return pd.DataFrame(recs, columns=["time", "Open", "High", "Low", "Close"]).set_index("time")

    def option_bars(self, expiry, strike, right, day):
        if expiry in self.dead or day not in self.paths:
            return pd.DataFrame(columns=["Open", "High", "Low", "Close"])
        p = self.paths[day]
        prem = [max(5.0, 80 + (0.5 if right == "call" else -0.5) * (x - strike)) for x in p]
        recs = []
        for m in range(MINUTES):
            o, c = prem[m], prem[m + 1]
            hi, lo = max(o, c), min(o, c)
            if self.wide_bar_at == (day, m):
                hi, lo = o * 2, o * 0.5
            if self.gap_at == (day, m):
                lo, c = o * 0.5, o * 0.5
            recs.append((self._t(day, m), o, hi, lo, c))
        return pd.DataFrame(recs, columns=["time", "Open", "High", "Low", "Close"]).set_index("time")

    def option_seconds(self, expiry, strike, right, start, end):
        """Seconds interpolated inside each minute bar; scripted for the wide / gap minutes."""
        day = start.date()
        bars = self.option_bars(expiry, strike, right, day)
        recs = []
        for t, b in bars.iterrows():
            for k in range(60):
                ts = t + dt.timedelta(seconds=k)
                if not start <= ts <= end:
                    continue
                o = b["Open"]
                if self.wide_bar_at == (day, (t - dt.datetime.combine(day, OPEN)).seconds // 60):
                    first, second = (b["Low"], b["High"]) if self.wide_first == "stop" else (b["High"], b["Low"])
                    p = o if k < 10 else first if k < 30 else second
                elif self.gap_at == (day, (t - dt.datetime.combine(day, OPEN)).seconds // 60):
                    p = o if k < 20 else b["Low"]  # jumps straight through the stop at second 20
                else:
                    p = o + (b["Close"] - o) * k / 60
                recs.append((ts, p, p, p, p))
        return pd.DataFrame(recs, columns=["time", "Open", "High", "Low", "Close"]).set_index("time")


def at_close(d):
    return dt.datetime.combine(d, dt.time(16, 0), tzinfo=IST)


CFG = PaperConfig()
DAYS = sessions(dt.date(2026, 6, 1), 12)  # Mon 1 Jun .. ; RSI warms up on the first few flat days


def run(md, upto, cfg=CFG, replays=None):
    save = (lambda tid, data: replays.__setitem__(tid, data)) if replays is not None else None
    ledger = engine.step(md, cfg, None, at_close(DAYS[4]), save)  # record opens on DAYS[4]
    for d in DAYS[5:upto + 1]:
        ledger = engine.step(md, cfg, ledger, at_close(d), save)
    return ledger


def test_quiet_days_record_no_trades():
    ledger = run(FakeMarket(DAYS), 8)
    assert ledger["trades"] == []
    assert [e[0] for e in ledger["equity"]] == [d.isoformat() for d in DAYS[4:9]]
    assert ledger["start"] == DAYS[4].isoformat()


def test_dip_then_rebound_opens_a_call_and_hits_the_target():
    replays = {}
    ledger = run(FakeMarket(DAYS, {DAYS[6]: "dip_rebound"}), 6, replays=replays)
    (t,) = ledger["trades"]
    assert t["right"] == "call" and t["exit_reason"] == "target" and t["pnl"] > 0
    assert t["rsi"] < CFG.oversold
    assert t["exit_price"] == pytest.approx(t["target_price"])  # a target is a limit: no slippage
    assert dt.datetime.fromisoformat(t["entry_time"]) >= dt.datetime.fromisoformat(t["signal_time"])
    assert t["id"] in replays and replays[t["id"]]["option"] and replays[t["id"]]["rsi"]


def test_dip_that_keeps_falling_hits_the_stop():
    (t,) = run(FakeMarket(DAYS, {DAYS[6]: "dip_fall"}), 6)["trades"]
    assert t["exit_reason"] == "stop" and t["pnl"] < 0
    # the first print at/below the level: at the stop or a touch worse, never better
    level = costs.slipped(t["stop_price"], "sell", CFG)
    assert level * 0.99 <= t["exit_price"] <= level


def test_going_nowhere_squares_off_at_1515():
    (t,) = run(FakeMarket(DAYS, {DAYS[6]: "dip_flat"}), 6)["trades"]
    assert t["exit_reason"] == "time"
    assert dt.datetime.fromisoformat(t["exit_time"]).time() == dt.time(15, 15)


def test_spike_opens_a_put():
    (t,) = run(FakeMarket(DAYS, {DAYS[6]: "spike_fade"}), 6)["trades"]
    assert t["right"] == "put" and t["rsi"] > CFG.overbought


def _entry_minute():
    first = run(FakeMarket(DAYS, {DAYS[6]: "dip_rebound"}), 6)["trades"][0]
    return int((dt.datetime.fromisoformat(first["entry_time"]) - dt.datetime.combine(DAYS[6], OPEN)).total_seconds() // 60)


@pytest.mark.parametrize("first", ["stop", "target"])
def test_seconds_decide_which_level_came_first(first):
    m = _entry_minute() + 1
    md = FakeMarket(DAYS, {DAYS[6]: "dip_rebound"}, wide_bar_at=(DAYS[6], m), wide_first=first)
    (t,) = run(md, 6)["trades"]
    assert t["exit_reason"] == first and t["resolution"] == "second"
    assert dt.datetime.fromisoformat(t["exit_time"]) == dt.datetime.combine(DAYS[6], OPEN) + dt.timedelta(minutes=m, seconds=10)


def test_without_seconds_both_in_a_minute_counts_as_stop():
    md = FakeMarket(DAYS, {DAYS[6]: "dip_rebound"}, wide_bar_at=(DAYS[6], _entry_minute() + 1), seconds=False)
    (t,) = run(md, 6)["trades"]
    assert t["exit_reason"] == "stop" and t["resolution"] == "minute"


def test_a_stop_that_gaps_fills_at_the_gap_not_the_level():
    md = FakeMarket(DAYS, {DAYS[6]: "dip_flat"}, gap_at=(DAYS[6], _entry_minute() + 2))
    (t,) = run(md, 6)["trades"]
    assert t["exit_reason"] == "stop"
    assert t["exit_price"] < costs.slipped(t["stop_price"], "sell", CFG) * 0.9  # far worse than the level


def test_entries_respect_the_time_window():
    cfg = PaperConfig(first_entry="11:00")  # the dip's signal comes around 10:1x
    ledger = run(FakeMarket(DAYS, {DAYS[6]: "dip_rebound"}), 6, cfg=cfg)
    for t in ledger["trades"]:
        assert dt.datetime.fromisoformat(t["signal_time"]).time() >= dt.time(11, 0)


def test_one_trade_a_day_by_default():
    ledger = run(FakeMarket(DAYS, {DAYS[6]: "dip_flat"}), 6)
    assert sum(t["date"] == DAYS[6].isoformat() for t in ledger["trades"]) == 1


def test_catch_up_matches_daily_runs_and_is_idempotent():
    scen = {DAYS[5]: "dip_rebound", DAYS[7]: "dip_fall", DAYS[9]: "spike_fade"}
    daily = run(FakeMarket(DAYS, scen), 10)
    md = FakeMarket(DAYS, scen)
    caught = engine.step(md, CFG, None, at_close(DAYS[4]))
    caught = engine.step(md, CFG, caught, at_close(DAYS[10]))  # backend was off for a week
    assert caught["trades"] == daily["trades"] and caught["equity"] == daily["equity"]
    again = engine.step(md, CFG, caught, at_close(DAYS[10]))
    assert again["trades"] == daily["trades"] and len(again["equity"]) == len(daily["equity"])


def test_before_the_close_simulates_only_finished_sessions():
    ledger = engine.step(FakeMarket(DAYS), CFG, None, dt.datetime.combine(DAYS[5], dt.time(11, 0), tzinfo=IST))
    assert ledger["last_processed"] == DAYS[4].isoformat()


def test_holiday_moved_expiry_falls_back_a_day():
    day = DAYS[6]
    tuesday = engine.next_expiry(day, 1)
    (t,) = run(FakeMarket(DAYS, {day: "dip_rebound"}, dead_expiries={tuesday}), 6)["trades"]
    assert t["expiry"] == (tuesday - dt.timedelta(days=1)).isoformat() or t["expiry"] == (tuesday - dt.timedelta(days=2)).isoformat()


def test_equity_is_capital_plus_realized():
    ledger = run(FakeMarket(DAYS, {DAYS[5]: "dip_rebound", DAYS[7]: "dip_fall"}), 9)
    assert ledger["equity"][-1][1] == pytest.approx(CFG.capital + sum(t["pnl"] for t in ledger["trades"]), abs=0.05)


def test_charges_components():
    cfg = PaperConfig()
    buy, sell = costs.charges(10_000, "buy", cfg), costs.charges(10_000, "sell", cfg)
    assert sell > buy  # STT is sell-side only for options
    assert buy == pytest.approx(20 + 3.503 + 0.01 + 0.3 + (20 + 3.503 + 0.01) * 0.18, abs=0.01)
