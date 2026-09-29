"""Paper engine tests against a synthetic market (no Breeze login needed).

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


def sessions(start: dt.date, n: int, holidays=()) -> list[dt.date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5 and d not in holidays:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


class FakeMarket:
    """Nifty rises for `up` sessions then falls; options priced as intrinsic + a little time value."""

    def __init__(self, days, up=70, dead_expiries=()):
        self.days = days
        closes = [20000 + 40 * i if i < up else 20000 + 40 * up - 60 * (i - up) for i in range(len(days))]
        self.df = pd.DataFrame({"Open": [c - 10 for c in closes], "High": [c + 50 for c in closes],
                                "Low": [c - 50 for c in closes], "Close": closes}, index=days)
        self.dead = set(dead_expiries)  # expiries with no contracts listed (holiday-moved weeklies)
        self.calls = 0

    def index_daily(self, start, end):
        return self.df[(self.df.index >= start) & (self.df.index <= end)]

    def _price(self, expiry, strike, right, day, spot):
        if expiry in self.dead or day not in self.df.index or day > expiry:
            return None
        intrinsic = max(spot - strike, 0) if right == "call" else max(strike - spot, 0)
        return round(intrinsic + 20 * math.sqrt((expiry - day).days + 1), 2)

    def option_open(self, expiry, strike, right, day):
        self.calls += 1
        return self._price(expiry, strike, right, day, self.df.loc[day, "Open"] if day in self.df.index else 0)

    def option_close(self, expiry, strike, right, day):
        self.calls += 1
        return self._price(expiry, strike, right, day, self.df.loc[day, "Close"] if day in self.df.index else 0)


def at_close(d: dt.date) -> dt.datetime:
    return dt.datetime.combine(d, dt.time(16, 0), tzinfo=IST)


CFG = PaperConfig(fast=5, slow=20)
DAYS = sessions(dt.date(2026, 1, 5), 120)


def run_daily(md, start_idx, end_idx, cfg=CFG):
    ledger = engine.step(md, cfg, None, at_close(DAYS[start_idx]))
    for d in DAYS[start_idx + 1:end_idx + 1]:
        ledger = engine.step(md, cfg, ledger, at_close(d))
    return ledger


def test_first_run_only_decides():
    md = FakeMarket(DAYS)
    ledger = engine.step(md, CFG, None, at_close(DAYS[30]))
    assert ledger["start"] == DAYS[30].isoformat()
    assert ledger["trades"] == [] and ledger["position"] is None
    assert ledger["pending"]["reason"] == "open" and ledger["pending"]["target"]["right"] == "call"


def test_fill_at_next_open_with_slippage_and_charges():
    md = FakeMarket(DAYS)
    ledger = run_daily(md, 30, 31)
    t = ledger["trades"][0]
    assert t["date"] == DAYS[31].isoformat() and t["action"] == "open" and t["right"] == "call"
    assert t["price"] == costs.slipped(t["raw_price"], "buy", CFG)
    assert ledger["cash"] == pytest.approx(CFG.capital - t["price"] * t["qty"] - t["charges"], abs=0.01)
    assert dt.date.fromisoformat(t["expiry"]) > DAYS[31]  # never opens a contract expiring that day


def test_switch_to_put_when_trend_flips():
    md = FakeMarket(DAYS, up=70)
    ledger = run_daily(md, 30, 110)
    switches = [t for t in ledger["trades"] if t["reason"] == "switch"]
    assert switches, "trend flipped but the position never switched"
    closed, opened = switches[0], switches[1]
    assert closed["action"] == "close" and opened["action"] == "open"
    assert closed["right"] == "call" and opened["right"] == "put" and closed["date"] == opened["date"]


def test_rolls_before_expiry_and_never_holds_through_it():
    md = FakeMarket(DAYS)
    ledger = run_daily(md, 30, 60)
    assert any(t["reason"] == "roll" for t in ledger["trades"])
    for t in ledger["trades"]:
        if t["action"] == "close":
            assert dt.date.fromisoformat(t["date"]) < dt.date.fromisoformat(t["expiry"])
    assert not any(t["reason"] == "expired" for t in ledger["trades"])


def test_catch_up_matches_daily_runs():
    daily = run_daily(FakeMarket(DAYS), 30, 90)
    md = FakeMarket(DAYS)
    caught = engine.step(md, CFG, None, at_close(DAYS[30]))
    caught = engine.step(md, CFG, caught, at_close(DAYS[90]))  # backend was down for two months
    assert caught["trades"] == daily["trades"]
    assert caught["equity"] == daily["equity"]
    assert caught["cash"] == daily["cash"]


def test_step_is_idempotent():
    md = FakeMarket(DAYS)
    ledger = run_daily(md, 30, 50)
    before = repr(ledger)
    again = engine.step(md, CFG, ledger, at_close(DAYS[50]))
    assert repr(again) == before


def test_before_the_close_uses_previous_session():
    md = FakeMarket(DAYS)
    ledger = engine.step(md, CFG, None, dt.datetime.combine(DAYS[40], dt.time(11, 0), tzinfo=IST))
    assert ledger["start"] == DAYS[39].isoformat()


def test_holiday_moved_expiry_falls_back_to_previous_day():
    first_fill = DAYS[31]
    tuesday = engine.next_expiry(engine.next_weekday(first_fill), 1)
    md = FakeMarket(DAYS, dead_expiries={tuesday})  # that week's weekly moved to Monday
    ledger = run_daily(md, 30, 31)
    opened = ledger["trades"][0]
    assert opened["expiry"] == (tuesday - dt.timedelta(days=1)).isoformat()


def test_no_price_means_stay_flat_and_note():
    md = FakeMarket(DAYS)
    md.option_open = lambda *a: None
    ledger = run_daily(md, 30, 31)
    assert ledger["position"] is None and ledger["notes"]


def test_equity_accounts_for_every_rupee():
    md = FakeMarket(DAYS)
    ledger = run_daily(md, 30, 100)
    realized = sum(t["pnl"] for t in ledger["trades"] if t["action"] == "close")
    pos = ledger["position"]
    open_value = pos["mark"] * pos["qty"] if pos else 0
    open_cost = pos["entry_cost"] if pos else 0
    assert ledger["equity"][-1][1] == pytest.approx(CFG.capital + realized + open_value - open_cost, abs=0.05)


def test_charges_components():
    cfg = PaperConfig()
    buy, sell = costs.charges(10_000, "buy", cfg), costs.charges(10_000, "sell", cfg)
    assert sell > buy  # STT is sell-side only for options
    assert buy == pytest.approx(20 + 3.503 + 0.01 + 0.3 + (20 + 3.503 + 0.01) * 0.18, abs=0.01)
