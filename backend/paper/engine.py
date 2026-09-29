"""The daily cycle of the options paper trader.

For each settled session d, in order:
  1. fill whatever was decided at the previous close, at d's 09:15 option prices (+ slippage, + charges)
  2. mark the open position at d's option close; the benchmark is Nifty itself
  3. decide at d's close what to hold from the next open:
       Nifty fast average above slow -> ATM call, else ATM put, on the nearest weekly expiry with a
       session to spare after the fill. Hold until the trend flips (switch) or until the last session
       before expiry (roll) - never on expiry day itself. Strike is fixed while a position is held.

The paper record starts at the first run and is never backfilled - a backfilled record is a backtest.
Days are processed from Breeze history, so downtime or a missed login is caught up on the next run.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import pandas as pd

from . import costs
from .config import PaperConfig
from .market import MarketData

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
SETTLED = dt.time(15, 45)  # NSE closes 15:30; give the data a few minutes
LOOKBACK_DAYS = 200  # calendar days of index history fetched per run (enough for a 50-day average)


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def last_settled_day(now: dt.datetime) -> dt.date:
    return now.date() if now.time() >= SETTLED else now.date() - dt.timedelta(days=1)


def next_weekday(d: dt.date) -> dt.date:
    d += dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def next_expiry(after: dt.date, weekday: int) -> dt.date:
    """First expiry weekday strictly after `after`."""
    d = after + dt.timedelta(days=1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d


def trend_up(closes: pd.Series, cfg: PaperConfig) -> Optional[bool]:
    if len(closes) < cfg.slow:
        return None
    return bool(closes.iloc[-cfg.fast:].mean() > closes.iloc[-cfg.slow:].mean())


def contract_label(c: dict) -> str:
    return f"NIFTY {c['strike']} {'CE' if c['right'] == 'call' else 'PE'} {dt.date.fromisoformat(c['expiry']):%d %b}"


# ------------------------------------------------------------------ ledger lifecycle

def new_ledger(cfg: PaperConfig, df: pd.DataFrame) -> dict:
    d0 = df.index[-1]
    ledger = {
        "version": 1,
        "start": d0.isoformat(),
        "config": cfg.as_dict(),
        "cash": cfg.capital,
        "position": None,
        "pending": None,
        "bench_base": float(df["Close"].iloc[-1]),
        "last_processed": d0.isoformat(),
        "equity": [[d0.isoformat(), cfg.capital, cfg.capital]],
        "trades": [],
        "notes": [],
    }
    decide(ledger, cfg, df)
    return ledger


def step(md: MarketData, cfg: PaperConfig, ledger: Optional[dict], now: Optional[dt.datetime] = None) -> dict:
    """Bring the ledger up to the latest settled session. Idempotent."""
    end = last_settled_day(now or now_ist())
    df = md.index_daily(end - dt.timedelta(days=LOOKBACK_DAYS), end)
    df = df[df.index <= end]
    if df.empty:
        raise RuntimeError("no Nifty bars returned - is the Breeze session logged in?")
    if ledger is None:
        return new_ledger(cfg, df)
    last = dt.date.fromisoformat(ledger["last_processed"])
    for d in [d for d in df.index if d > last]:
        process_day(ledger, cfg, md, df.loc[:d])
    return ledger


# ------------------------------------------------------------------ one session

def process_day(ledger: dict, cfg: PaperConfig, md: MarketData, df: pd.DataFrame) -> None:
    d = df.index[-1]
    pending, ledger["pending"] = ledger["pending"], None
    if pending:
        if ledger["position"] and pending["reason"] in ("switch", "roll"):
            _close(ledger, cfg, md, d, pending["reason"], pending["decided_on"])
        if pending.get("target"):
            _open(ledger, cfg, md, d, pending)

    pos = ledger["position"]
    if pos:
        px = md.option_close(dt.date.fromisoformat(pos["expiry"]), pos["strike"], pos["right"], d)
        if px is not None:
            pos["mark"] = px
        if dt.date.fromisoformat(pos["expiry"]) <= d:  # a roll failed to fill; settle at the expiry close
            _close(ledger, cfg, md, d, "expired", d.isoformat(), price=pos["mark"])
            pos = None

    value = ledger["cash"] + (pos["mark"] * pos["qty"] if pos else 0.0)
    bench = ledger["config"]["capital"] * float(df["Close"].iloc[-1]) / ledger["bench_base"]
    ledger["equity"].append([d.isoformat(), round(value, 2), round(bench, 2)])

    decide(ledger, cfg, df)
    ledger["last_processed"] = d.isoformat()


def decide(ledger: dict, cfg: PaperConfig, df: pd.DataFrame) -> None:
    """At the close of df's last session, queue what to hold from the next open."""
    d, close = df.index[-1], float(df["Close"].iloc[-1])
    up = trend_up(df["Close"], cfg)
    if up is None:
        return
    right = "call" if up else "put"
    fill_day = next_weekday(d)
    # Never hold on expiry day (its prices swing wildly): open only contracts with a session to spare
    # after the fill, and roll at the open of the last session before expiry.
    after_fill = next_weekday(fill_day)
    target = {"right": right, "strike": int(round(close / cfg.strike_step) * cfg.strike_step),
              "expiry": next_expiry(after_fill, cfg.expiry_weekday).isoformat()}
    pos = ledger["position"]
    reason = None
    if pos is None:
        reason = "open"
    elif pos["right"] != right:
        reason = "switch"
    elif dt.date.fromisoformat(pos["expiry"]) <= after_fill:
        reason = "roll"
    if reason:
        ledger["pending"] = {"decided_on": d.isoformat(), "reason": reason, "target": target,
                             "trend": "up" if up else "down", "nifty_close": close}


# ------------------------------------------------------------------ fills

def _open(ledger: dict, cfg: PaperConfig, md: MarketData, d: dt.date, pending: dict) -> None:
    t = dict(pending["target"])
    expiry = dt.date.fromisoformat(t["expiry"])
    if expiry <= next_weekday(d):  # the fill slipped past a holiday; keep a session in hand
        expiry = next_expiry(next_weekday(d), cfg.expiry_weekday)
    raw = None
    for shift in (0, 1, 2):  # a holiday moves the weekly expiry to the previous trading day
        cand = expiry - dt.timedelta(days=shift)
        if cand <= d:
            break
        raw = md.option_open(cand, t["strike"], t["right"], d)
        if raw is not None:
            expiry = cand
            break
    t["expiry"] = expiry.isoformat()
    if raw is None:
        ledger["notes"].append({"date": d.isoformat(), "note": f"no opening price for {contract_label(t)}; stayed flat"})
        return
    qty = cfg.lots * cfg.lot_size
    price = costs.slipped(raw, "buy", cfg)
    fee = costs.charges(price * qty, "buy", cfg)
    ledger["cash"] = round(ledger["cash"] - price * qty - fee, 2)
    ledger["position"] = {**t, "qty": qty, "entry_date": d.isoformat(), "entry_price": price,
                          "entry_cost": round(price * qty + fee, 2), "mark": raw}
    ledger["trades"].append({"date": d.isoformat(), "action": "open", "reason": pending["reason"], **t,
                             "qty": qty, "price": price, "raw_price": raw, "charges": fee,
                             "decided_on": pending["decided_on"], "trend": pending.get("trend"),
                             "nifty_close": pending.get("nifty_close")})


def _close(ledger: dict, cfg: PaperConfig, md: MarketData, d: dt.date, reason: str, decided_on: str,
           price: Optional[float] = None) -> None:
    pos = ledger["position"]
    expiry = dt.date.fromisoformat(pos["expiry"])
    raw = price if price is not None else md.option_open(expiry, pos["strike"], pos["right"], d)
    if raw is None:  # no trade at the open: take the day's close rather than keep a stale position
        raw = md.option_close(expiry, pos["strike"], pos["right"], d)
    if raw is None:
        raw = pos["mark"]
    qty = pos["qty"]
    fill = costs.slipped(raw, "sell", cfg)
    fee = costs.charges(fill * qty, "sell", cfg)
    proceeds = fill * qty - fee
    ledger["cash"] = round(ledger["cash"] + proceeds, 2)
    pnl = proceeds - pos["entry_cost"]
    ledger["trades"].append({"date": d.isoformat(), "action": "close", "reason": reason,
                             "right": pos["right"], "strike": pos["strike"], "expiry": pos["expiry"], "qty": qty,
                             "price": fill, "raw_price": raw, "charges": fee, "decided_on": decided_on,
                             "entry_date": pos["entry_date"], "entry_price": pos["entry_price"],
                             "pnl": round(pnl, 2), "pnl_pct": round(pnl / pos["entry_cost"] * 100, 2)})
    ledger["position"] = None
