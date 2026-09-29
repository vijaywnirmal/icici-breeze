"""Intraday options paper trader: one simulated session at a time, from Breeze minute history.

For each settled session:
  1. signal  - Nifty 5-minute RSI (warmed up on prior sessions). The first completed bar between
               first_entry and last_entry with RSI < oversold opens an ATM call; RSI > overbought, a put.
  2. open    - at the option's 1-minute bar starting when that 5-minute bar closes (+ slippage)
  3. hold    - minute by minute: stop if the low reaches -stop_pct, target if the high reaches +target_pct
               (both in one minute counts as the stop - the conservative reading), else close at square_off
  4. record  - the trade with charges, and a replay file (option minutes around the trade, Nifty bars, RSI)
               that the Shorts pipeline animates

Because everything is priced from history, the engine can run after the close or days later; missed
sessions are processed in order on the next run. The record starts at the first run and is never
backfilled - a backfilled record would just be a backtest.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import numpy as np
import pandas as pd

from . import costs
from .config import PaperConfig
from .market import MarketData

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
SETTLED = dt.time(15, 45)  # NSE closes 15:30; give the minute data a few minutes
WARMUP_DAYS = 7  # calendar days of earlier 5-minute bars used to warm up the RSI
CONTEXT_MIN = 30  # minutes of option prices kept before the entry / after the exit, for the replay


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def last_settled_day(now: dt.datetime) -> dt.date:
    return now.date() if now.time() >= SETTLED else now.date() - dt.timedelta(days=1)


def next_expiry(after: dt.date, weekday: int) -> dt.date:
    """First expiry weekday strictly after `after`."""
    d = after + dt.timedelta(days=1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d


def rsi(close: pd.Series, n: int) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    out = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    return out.where(loss != 0, 100.0)


def _hhmm(s: str) -> dt.time:
    return dt.datetime.strptime(s, "%H:%M").time()


def contract_label(c: dict) -> str:
    return f"NIFTY {c['strike']} {'CE' if c['right'] == 'call' else 'PE'} {dt.date.fromisoformat(c['expiry']):%d %b}"


# ------------------------------------------------------------------ ledger lifecycle

def new_ledger(cfg: PaperConfig, start: dt.date, bench_base: float) -> dict:
    return {"version": 2, "start": start.isoformat(), "config": cfg.as_dict(), "bench_base": bench_base,
            "last_processed": None, "equity": [], "trades": [], "notes": []}


def step(md: MarketData, cfg: PaperConfig, ledger: Optional[dict], now: Optional[dt.datetime] = None,
         save_replay=None) -> dict:
    """Simulate every settled session not yet in the ledger. Idempotent.

    save_replay(trade_id, payload) persists the replay data (ledger.py writes it next to the ledger).
    """
    end = last_settled_day(now or now_ist())
    daily = md.index_daily(end - dt.timedelta(days=30), end)
    daily = daily[daily.index <= end]
    if daily.empty:
        raise RuntimeError("no Nifty bars returned - is the Breeze session logged in?")
    if ledger is None:
        # open the record on the latest settled session; the benchmark starts at the close before it
        start = daily.index[-1]
        base = float(daily["Close"].iloc[-2]) if len(daily) > 1 else float(daily["Open"].iloc[-1])
        ledger = new_ledger(cfg, start, base)
    last = dt.date.fromisoformat(ledger["last_processed"]) if ledger["last_processed"] else None
    for day in [d for d in daily.index if (last is None and d >= dt.date.fromisoformat(ledger["start"]))
                or (last is not None and d > last)]:
        process_day(ledger, cfg, md, day, float(daily.loc[day, "Close"]), save_replay)
    return ledger


# ------------------------------------------------------------------ one session

def process_day(ledger: dict, cfg: PaperConfig, md: MarketData, day: dt.date, nifty_close: float,
                save_replay=None) -> None:
    bars = md.index_bars(day - dt.timedelta(days=WARMUP_DAYS), day, cfg.bar_interval)
    trades_today = []
    if not bars.empty:
        r = rsi(bars["Close"], cfg.rsi_period)
        today = bars[[t.date() == day for t in bars.index]]
        bar_len = dt.timedelta(minutes=int("".join(ch for ch in cfg.bar_interval if ch.isdigit()) or 5))
        from_t, to_t = _hhmm(cfg.first_entry), _hhmm(cfg.last_entry)
        busy_until = None
        for t in today.index:
            if len(trades_today) >= cfg.max_trades_per_day:
                break
            signal_at = t + bar_len  # the bar is only complete at its close
            if not (from_t <= signal_at.time() <= to_t) or (busy_until and signal_at < busy_until):
                continue
            v = r.loc[t]
            if pd.isna(v) or cfg.oversold <= v <= cfg.overbought:
                continue
            right = "call" if v < cfg.oversold else "put"
            trade = _trade(ledger, cfg, md, day, signal_at, right, float(today.loc[t, "Close"]), float(v),
                           today, r.loc[today.index], save_replay)
            if trade:
                trades_today.append(trade)
                busy_until = dt.datetime.fromisoformat(trade["exit_time"])

    realized = sum(t["pnl"] for t in ledger["trades"])
    cap = ledger["config"]["capital"]
    ledger["equity"].append([day.isoformat(), round(cap + realized, 2),
                             round(cap * nifty_close / ledger["bench_base"], 2)])
    ledger["last_processed"] = day.isoformat()


def _contract_bars(md, cfg, day, strike, right):
    """Nearest weekly after today; a holiday moves a weekly to the previous trading day."""
    expiry = next_expiry(day, cfg.expiry_weekday)
    for shift in (0, 1, 2):
        cand = expiry - dt.timedelta(days=shift)
        if cand <= day:
            break
        bars = md.option_bars(cand, strike, right, day)
        if bars is not None and not bars.empty:
            return cand, bars
    return expiry, None


def _trade(ledger, cfg, md, day, signal_at, right, nifty, rsi_value, today, rsi_today, save_replay) -> Optional[dict]:
    strike = int(round(nifty / cfg.strike_step) * cfg.strike_step)
    expiry, ob = _contract_bars(md, cfg, day, strike, right)
    label = contract_label({"strike": strike, "right": right, "expiry": expiry.isoformat()})
    if ob is None:
        ledger["notes"].append({"date": day.isoformat(), "note": f"signal at {signal_at:%H:%M} but no prices for {label}"})
        return None
    after = ob[ob.index >= signal_at]
    if after.empty:
        ledger["notes"].append({"date": day.isoformat(), "note": f"no minute bars for {label} after {signal_at:%H:%M}"})
        return None

    qty = cfg.lots * cfg.lot_size
    entry_time = after.index[0]
    entry = costs.slipped(float(after["Open"].iloc[0]), "buy", cfg)
    target, stop = entry * (1 + cfg.target_pct / 100), entry * (1 - cfg.stop_pct / 100)
    square = dt.datetime.combine(day, _hhmm(cfg.square_off))

    exit_time, raw, reason = None, None, None
    for t, bar in after.iterrows():
        if t >= square:
            exit_time, raw, reason = t, float(bar["Open"]), "time"
            break
        hit_stop, hit_target = bar["Low"] <= stop, bar["High"] >= target
        if hit_stop:  # both in one minute: assume the stop came first
            exit_time, raw, reason = t, stop, "stop"
            break
        if hit_target:
            exit_time, raw, reason = t, target, "target"
            break
    if exit_time is None:  # data ran out before the square-off
        exit_time, raw, reason = after.index[-1], float(after["Close"].iloc[-1]), "time"
    exit_price = round(raw, 2) if reason == "target" else costs.slipped(raw, "sell", cfg)

    buy_fee = costs.charges(entry * qty, "buy", cfg)
    sell_fee = costs.charges(exit_price * qty, "sell", cfg)
    cost_in = entry * qty + buy_fee
    pnl = exit_price * qty - sell_fee - cost_in
    trade_id = f"{day.isoformat()}-{sum(1 for t in ledger['trades'] if t['date'] == day.isoformat()) + 1}"
    trade = {
        "id": trade_id, "date": day.isoformat(), "right": right, "strike": strike, "expiry": expiry.isoformat(),
        "qty": qty, "signal_time": signal_at.isoformat(), "rsi": round(rsi_value, 1), "nifty_at_signal": nifty,
        "entry_time": entry_time.isoformat(), "entry_price": entry, "target_price": round(target, 2),
        "stop_price": round(stop, 2), "exit_time": exit_time.isoformat(), "exit_price": exit_price,
        "exit_reason": reason, "held_minutes": int((exit_time - entry_time).total_seconds() // 60),
        "charges": round(buy_fee + sell_fee, 2), "pnl": round(pnl, 2), "pnl_pct": round(pnl / cost_in * 100, 2),
    }
    ledger["trades"].append(trade)

    if save_replay:
        lo, hi = entry_time - dt.timedelta(minutes=CONTEXT_MIN), exit_time + dt.timedelta(minutes=CONTEXT_MIN)
        win = ob[(ob.index >= lo) & (ob.index <= hi)]
        save_replay(trade_id, {
            "trade": trade,
            "option": [[t.isoformat(), *map(float, row)] for t, row in win[["Open", "High", "Low", "Close"]].iterrows()],
            "nifty": [[t.isoformat(), float(c)] for t, c in today["Close"].items()],
            "rsi": [[t.isoformat(), None if pd.isna(v) else round(float(v), 2)] for t, v in rsi_today.items()],
            "levels": {"oversold": cfg.oversold, "overbought": cfg.overbought},
        })
    return trade
