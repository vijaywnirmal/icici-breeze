"""Backtest the paper strategy over a range of past sessions, through the same engine the paper trader runs.

Every session in [start, end] goes through engine.process_day exactly as the live record does - same signal,
contract choice, 1-second stop/target resolution, slippage and charges - so a backtest and the paper record
can be compared directly. What a backtest adds:

  - history-aware contracts: Nifty weeklies expired on Thursdays until NSE moved them to Tuesdays
    (first Tuesday expiry 2 Sep 2025); each session trades the weekly that actually existed
  - index bars fetched once for the whole range, option prices cached on disk (data/paper/cache/) so re-runs
    and parameter sweeps don't download them again, and a throttle that stays under Breeze's rate limit
  - a report: win rate, profit factor, expectancy, drawdown, Sharpe, a t-statistic for "is the mean trade
    different from zero", month by month, and in-sample / out-of-sample halves around a split date
  - sweeps over a grid of settings, ranked on the in-sample period and shown next to their out-of-sample
    results, so a setting that only fits the past is visible as one

Size stays at cfg.lots x cfg.lot_size throughout (NSE has revised the Nifty lot size several times; a fixed
size keeps sessions comparable). Per-trade pnl_pct is independent of it.

    python -m backend.paper.backtest --start 2025-01-01 --end 2025-12-31 --split 2025-10-01
    python -m backend.paper.backtest --start 2025-01-01 --end 2025-12-31 --set target_pct=40 --set stop_pct=25
    python -m backend.paper.backtest --start 2025-01-01 --end 2025-12-31 --split 2025-10-01 \\
        --grid oversold=15,20,25 --grid target_pct=20,30,40

Needs a Breeze session: BREEZE_API_KEY / BREEZE_API_SECRET from .env plus today's session token (--token, or
BREEZE_SESSION_TOKEN). The backend can also run one with its own session: POST /api/paper/backtest.
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import math
import os
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd

from .config import DATA_DIR, PaperConfig, load_config, with_overrides
from .engine import WARMUP_DAYS, new_ledger, next_expiry, process_day
from .market import COLS, BreezeMarket, MarketData

RESULTS = DATA_DIR / "backtests"
CACHE = DATA_DIR / "cache"
_NAME = re.compile(r"^[\w.-]{1,80}$")

# (first expiry date on this weekday, weekday). Thursday weeklies until NSE's move to Tuesday in Sep 2025.
NIFTY_WEEKLY_EXPIRY = [(dt.date.min, 3), (dt.date(2025, 9, 1), 1)]

Progress = Callable[[int, int, dt.date], None]


def expiry_weekday_for(day: dt.date, schedule=NIFTY_WEEKLY_EXPIRY) -> int:
    """Weekday of the nearest weekly expiring after `day`, under an expiry schedule that changed over time."""
    best = None
    for i, (since, wd) in enumerate(schedule):
        until = schedule[i + 1][0] if i + 1 < len(schedule) else dt.date.max
        e = next_expiry(day, wd)
        if since <= e < until and (best is None or e < best[0]):
            best = (e, wd)
    return best[1] if best else schedule[-1][1]


# ------------------------------------------------------------------ data

class ThrottledClient:
    """Spaces out get_historical_data_v2 calls (Breeze allows 100 a minute) and counts them."""

    def __init__(self, client, per_minute: int = 90):
        self.client = client
        self.gap = 60.0 / per_minute
        self.calls = 0
        self._last = 0.0

    def get_historical_data_v2(self, **kw):
        wait = self._last + self.gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.calls += 1
        return self.client.get_historical_data_v2(**kw)

    def __getattr__(self, name):
        return getattr(self.client, name)


class CachedMarket:
    """Option prices kept on disk, so re-runs and sweeps don't download them again. Only non-empty answers
    are cached: BreezeMarket returns an empty frame for errors as well as for contracts that never traded."""

    def __init__(self, md: MarketData, root: Path = CACHE, symbol: str = "NIFTY"):
        self.md = md
        self.root = root / symbol
        if getattr(md, "option_seconds", None) is None:
            self.option_seconds = None  # the engine falls back to minute bars

    def index_daily(self, start, end):
        return self.md.index_daily(start, end)

    def index_bars(self, start, end, interval):
        return self.md.index_bars(start, end, interval)

    def _cached(self, path: Path, fetch) -> pd.DataFrame:
        if path.exists():
            return pd.read_csv(path, index_col=0, parse_dates=True)
        df = fetch()
        if df is not None and not df.empty:
            path.parent.mkdir(parents=True, exist_ok=True)
            df[COLS].to_csv(path)
        return df

    def option_bars(self, expiry, strike, right, day):
        path = self.root / expiry.isoformat() / f"{strike}{right[0]}" / f"m-{day.isoformat()}.csv"
        return self._cached(path, lambda: self.md.option_bars(expiry, strike, right, day))

    def option_seconds(self, expiry, strike, right, start, end):
        path = self.root / expiry.isoformat() / f"{strike}{right[0]}" / f"s-{start:%Y%m%dT%H%M%S}-{end:%H%M%S}.csv"
        return self._cached(path, lambda: self.md.option_seconds(expiry, strike, right, start, end))


class _Preloaded:
    """Index bars fetched once for the whole range and sliced per session; option calls pass through."""

    def __init__(self, md: MarketData, daily: pd.DataFrame, bars: pd.DataFrame):
        self.md, self.daily, self.bars = md, daily, bars
        self.option_seconds = getattr(md, "option_seconds", None)

    def index_daily(self, start, end):
        return self.daily[(self.daily.index >= start) & (self.daily.index <= end)]

    def index_bars(self, start, end, interval):
        if self.bars.empty:
            return self.bars
        dates = self.bars.index.date
        return self.bars[(dates >= start) & (dates <= end)]

    def option_bars(self, expiry, strike, right, day):
        return self.md.option_bars(expiry, strike, right, day)


def _spans(start: dt.date, end: dt.date, days: int) -> Iterable[tuple[dt.date, dt.date]]:
    a = start
    while a <= end:
        b = min(end, a + dt.timedelta(days=days - 1))
        yield a, b
        a = b + dt.timedelta(days=1)


def _concat(parts: list[pd.DataFrame]) -> pd.DataFrame:
    parts = [p for p in parts if p is not None and not p.empty]
    if not parts:
        return pd.DataFrame(columns=COLS)
    df = pd.concat(parts)
    return df[~df.index.duplicated()].sort_index()


def load_index(md: MarketData, cfg: PaperConfig, start: dt.date, end: dt.date) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Nifty daily bars (from a little before start, for the benchmark base) and intraday bars (from the RSI
    warm-up before start), in chunks small enough for Breeze's ~1,000-row responses."""
    daily = _concat([md.index_daily(a, b) for a, b in _spans(start - dt.timedelta(days=10), end, 365)])
    minutes = int("".join(ch for ch in cfg.bar_interval if ch.isdigit()) or 5)
    per_day = 375 // minutes + 2  # plus the pre-open and post-close bars Breeze includes
    chunk = max(1, 900 // per_day)  # calendar days, so weekends only make the chunks smaller
    bars = _concat([md.index_bars(a, b, cfg.bar_interval)
                    for a, b in _spans(start - dt.timedelta(days=WARMUP_DAYS), end, chunk)])
    return daily, bars


# ------------------------------------------------------------------ run

def run_backtest(md: MarketData, cfg: PaperConfig, start: dt.date, end: dt.date, schedule=NIFTY_WEEKLY_EXPIRY,
                 index: Optional[tuple[pd.DataFrame, pd.DataFrame]] = None,
                 progress: Optional[Progress] = None) -> dict:
    """Simulate every session in [start, end]; returns a ledger shaped like the paper record's."""
    daily, bars = index if index is not None else load_index(md, cfg, start, end)
    days = [d for d in daily.index if start <= d <= end]
    if not days:
        raise RuntimeError(f"no Nifty sessions between {start} and {end} - is the Breeze session logged in?")
    before = daily[daily.index < days[0]]
    base = float(before["Close"].iloc[-1]) if not before.empty else float(daily.loc[days[0], "Open"])
    ledger = new_ledger(cfg, days[0], base)
    ledger.update(kind="backtest", end=days[-1].isoformat())
    pre = _Preloaded(md, daily, bars)
    have_bars = set(bars.index.date) if not bars.empty else set()
    for i, day in enumerate(days):
        if day not in have_bars:
            ledger["notes"].append({"date": day.isoformat(), "note": "no intraday Nifty bars - session not traded"})
        day_cfg = replace(cfg, expiry_weekday=expiry_weekday_for(day, schedule)) if schedule else cfg
        process_day(ledger, day_cfg, pre, day, float(daily.loc[day, "Close"]))
        if progress:
            progress(i + 1, len(days), day)
    return ledger


# ------------------------------------------------------------------ report

def _r(x, n=2):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(x, n)


def stats(trades: list[dict], equity: list, capital: float, start_value: float, start_bench: float) -> dict:
    """Figures for one stretch of a run: its trades and its equity rows ([date, value, benchmark])."""
    pnl = [t["pnl"] for t in trades]
    pct = [t["pnl_pct"] for t in trades]
    wins, losses = [p for p in pnl if p > 0], [p for p in pnl if p <= 0]
    n = len(pnl)
    mean_pct = sum(pct) / n if n else None
    sd_pct = (sum((p - mean_pct) ** 2 for p in pct) / (n - 1)) ** 0.5 if n > 1 else None
    values = [start_value] + [v for _, v, _ in equity]
    daily = [(b - a) / capital for a, b in zip(values, values[1:])]
    sd_day = (sum((d - sum(daily) / len(daily)) ** 2 for d in daily) / (len(daily) - 1)) ** 0.5 if len(daily) > 1 else 0
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        worst = min(worst, (v / peak - 1) * 100)
    streak = longest = 0
    for p in pnl:
        streak = streak + 1 if p <= 0 else 0
        longest = max(longest, streak)
    end_bench = equity[-1][2] if equity else start_bench
    return {
        "sessions": len(equity),
        "trades": n,
        "win_rate_pct": _r(len(wins) / n * 100, 1) if n else None,
        "avg_win": _r(sum(wins) / len(wins)) if wins else None,
        "avg_loss": _r(sum(losses) / len(losses)) if losses else None,
        "profit_factor": _r(sum(wins) / -sum(losses)) if losses and sum(losses) < 0 else None,
        "expectancy": _r(sum(pnl) / n) if n else None,  # rupees per trade, after charges
        "mean_trade_pct": _r(mean_pct),
        # mean / standard error: roughly, beyond +-2 the mean trade is unlikely to be zero by luck alone
        "t_stat": _r(mean_pct / (sd_pct / n ** 0.5)) if sd_pct else None,
        "net_pnl": _r(sum(pnl)),
        "charges": _r(sum(t["charges"] for t in trades)),
        "return_pct": _r((values[-1] - start_value) / capital * 100),
        "benchmark_return_pct": _r((end_bench / start_bench - 1) * 100),
        "max_drawdown_pct": _r(worst),
        "sharpe": _r(sum(daily) / len(daily) / sd_day * 252 ** 0.5) if sd_day else None,
        "max_losing_streak": longest,
        "avg_hold_min": _r(sum(t["held_minutes"] for t in trades) / n, 1) if n else None,
        "best_trade": _r(max(pnl)) if n else None,
        "worst_trade": _r(min(pnl)) if n else None,
        "by_exit": {k: sum(t["exit_reason"] == k for t in trades) for k in ("target", "stop", "time")},
        "by_right": {r: {"trades": sum(t["right"] == r for t in trades),
                         "pnl": _r(sum(t["pnl"] for t in trades if t["right"] == r))} for r in ("call", "put")},
    }


def _segment(ledger: dict, lo: Optional[dt.date], hi: Optional[dt.date]) -> dict:
    """stats() for sessions in [lo, hi), starting from the account and benchmark as they stood before lo."""
    cap = ledger["config"]["capital"]

    def inside(d):
        d = dt.date.fromisoformat(d)
        return (lo is None or d >= lo) and (hi is None or d < hi)

    eq = [e for e in ledger["equity"] if inside(e[0])]
    prior = [e for e in ledger["equity"] if lo is not None and dt.date.fromisoformat(e[0]) < lo]
    start_value, start_bench = (prior[-1][1], prior[-1][2]) if prior else (cap, cap)
    trades = [t for t in ledger["trades"] if inside(t["date"])]
    out = stats(trades, eq, cap, start_value, start_bench)
    out["from"], out["to"] = (eq[0][0], eq[-1][0]) if eq else (None, None)
    return out


def report(ledger: dict, split: Optional[dt.date] = None) -> dict:
    notes = ledger["notes"]
    out = {
        "period": {"start": ledger["start"], "end": ledger.get("end", ledger["last_processed"])},
        "overall": _segment(ledger, None, None),
        # sessions where a signal couldn't be traded because Breeze had no prices for the contract (the
        # engine retries on every later bar, so this counts sessions, not notes)
        "sessions_with_missed_signals": len({n["date"] for n in notes
                                             if "no prices" in n["note"] or "no minute bars" in n["note"]}),
        "sessions_without_data": sum("no intraday" in n["note"] for n in notes),
        "monthly": [],
    }
    if split is not None:
        out["in_sample"] = _segment(ledger, None, split)
        out["out_of_sample"] = _segment(ledger, split, None)
        out["split"] = split.isoformat()
    months = sorted({e[0][:7] for e in ledger["equity"]})
    for m in months:
        ts = [t for t in ledger["trades"] if t["date"].startswith(m)]
        out["monthly"].append({"month": m, "trades": len(ts), "pnl": _r(sum(t["pnl"] for t in ts)),
                               "wins": sum(t["pnl"] > 0 for t in ts)})
    return out


# ------------------------------------------------------------------ sweep

SWEEP_KEYS = ("trades", "win_rate_pct", "profit_factor", "mean_trade_pct", "t_stat", "net_pnl", "max_drawdown_pct")


def sweep(md: MarketData, base: PaperConfig, start: dt.date, end: dt.date, grid: dict[str, list],
          split: Optional[dt.date] = None, schedule=NIFTY_WEEKLY_EXPIRY,
          progress: Optional[Callable[[int, int, dict], None]] = None) -> list[dict]:
    """Every combination of the grid, ranked by in-sample net P&L (whole period without a split).
    With a split, the out-of-sample columns are the honest estimate: the ranking never saw them."""
    index = load_index(md, base, start, end)
    names = list(grid)
    combos = [dict(zip(names, vals)) for vals in itertools.product(*(grid[k] for k in names))]
    rows = []
    for i, params in enumerate(combos):
        cfg = with_overrides(base, params, strict=True)
        rep = report(run_backtest(md, cfg, start, end, schedule, index=index), split)
        row = {"params": params}
        for seg in ("in_sample", "out_of_sample") if split else ("overall",):
            row[seg] = {k: rep[seg][k] for k in SWEEP_KEYS}
        rows.append(row)
        if progress:
            progress(i + 1, len(combos), params)
    rank = "in_sample" if split else "overall"
    rows.sort(key=lambda r: r[rank]["net_pnl"] if r[rank]["net_pnl"] is not None else -math.inf, reverse=True)
    return rows


# ------------------------------------------------------------------ results on disk

def save_result(name: str, result: dict) -> Path:
    if not _NAME.match(name):
        raise ValueError(f"bad result name {name!r}")
    path = RESULTS / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


def load_result(name: str) -> Optional[dict]:
    if not _NAME.match(name):
        return None
    try:
        return json.loads((RESULTS / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_results() -> list[dict]:
    out = []
    for p in sorted(RESULTS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append({"name": p.stem, "kind": r.get("kind"), "start": r.get("start"), "end": r.get("end"),
                    "split": r.get("split"), "created": r.get("created")})
    return out


def execute(md: MarketData, cfg: PaperConfig, start: dt.date, end: dt.date, split: Optional[dt.date] = None,
            grid: Optional[dict[str, list]] = None, progress=None) -> dict:
    """One backtest or sweep, as the saved result: settings, report, and for a single run its trades,
    equity curve and notes."""
    result = {"kind": "sweep" if grid else "backtest", "start": start.isoformat(), "end": end.isoformat(),
              "split": split.isoformat() if split else None, "config": cfg.as_dict(),
              "created": dt.datetime.now().isoformat(timespec="seconds")}
    if grid:
        result.update(grid=grid, rows=sweep(md, cfg, start, end, grid, split, progress=progress))
    else:
        ledger = run_backtest(md, cfg, start, end, progress=progress)
        result.update(report=report(ledger, split), trades=ledger["trades"], equity=ledger["equity"],
                      notes=ledger["notes"])
    return result


# ------------------------------------------------------------------ command line

def _parse_value(v: str):
    out = []
    for part in v.split(","):
        part = part.strip()
        try:
            out.append(float(part) if any(c in part for c in ".eE") else int(part))
        except ValueError:
            out.append(part)
    return out


def _pairs(items: list[str], what: str) -> dict:
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"{what} expects name=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _fmt(v) -> str:
    return "-" if v is None else f"{v:,.2f}" if isinstance(v, float) else str(v)


def print_result(result: dict) -> None:
    if result["kind"] == "sweep":
        segs = ["in_sample", "out_of_sample"] if result["split"] else ["overall"]
        cols = ("trades", "win_rate_pct", "profit_factor", "t_stat", "net_pnl")
        head = ["params"] + [f"{s[:3]}:{k}" for s in segs for k in cols]
        table = [head]
        for row in result["rows"]:
            cells = [",".join(f"{k}={v}" for k, v in row["params"].items())]
            cells += [_fmt(row[s][k]) for s in segs for k in cols]
            table.append(cells)
        widths = [max(len(r[i]) for r in table) for i in range(len(head))]
        for r in table:
            print("  ".join(c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(r, widths))))
        return
    rep = result["report"]
    segs = [s for s in ("overall", "in_sample", "out_of_sample") if s in rep]
    keys = [k for k in rep["overall"] if not isinstance(rep["overall"][k], dict) and k not in ("from", "to")]
    print(f"{'':24}" + "".join(f"{s:>16}" for s in segs))
    for k in keys:
        print(f"{k:24}" + "".join(f"{_fmt(rep[s][k]):>16}" for s in segs))
    o = rep["overall"]
    print(f"\nexits: {o['by_exit']}   calls: {o['by_right']['call']}   puts: {o['by_right']['put']}")
    if rep["sessions_with_missed_signals"] or rep["sessions_without_data"]:
        print(f"sessions with signals but no option prices: {rep['sessions_with_missed_signals']}   "
              f"sessions without Nifty bars: {rep['sessions_without_data']}")
    print("\nmonth     trades  wins        pnl")
    for m in rep["monthly"]:
        print(f"{m['month']}  {m['trades']:>6}  {m['wins']:>4}  {m['pnl']:>10,.2f}")


def _login(token: str):
    from ..services.breeze_service import BreezeService
    key, secret = (os.getenv("BREEZE_API_KEY") or "").strip(), (os.getenv("BREEZE_API_SECRET") or "").strip()
    if not key or not secret:
        raise SystemExit("Set BREEZE_API_KEY and BREEZE_API_SECRET in .env")
    if not token:
        raise SystemExit("Pass today's session token with --token (or set BREEZE_SESSION_TOKEN)")
    service = BreezeService(api_key=key)
    res = service.login_and_fetch_profile(api_secret=secret, session_key=token)
    if not res.success:
        raise SystemExit(f"Breeze login failed: {res.error or res.message}")
    return service.client


def main(argv: Optional[list[str]] = None) -> int:
    from ..utils import config as _env  # noqa: F401  (loads .env)
    p = argparse.ArgumentParser(prog="python -m backend.paper.backtest", description=__doc__.split("\n\n")[0])
    p.add_argument("--start", type=dt.date.fromisoformat, required=True)
    p.add_argument("--end", type=dt.date.fromisoformat, required=True)
    p.add_argument("--split", type=dt.date.fromisoformat, help="first out-of-sample session")
    p.add_argument("--set", action="append", metavar="NAME=VALUE", help="override a setting (repeatable)")
    p.add_argument("--grid", action="append", metavar="NAME=V1,V2,...", help="sweep a setting (repeatable)")
    p.add_argument("--name", help="result file name under data/paper/backtests/")
    p.add_argument("--token", default=os.getenv("BREEZE_SESSION_TOKEN", ""))
    p.add_argument("--per-minute", type=int, default=90, help="Breeze calls per minute (limit is 100)")
    p.add_argument("--no-cache", action="store_true", help="don't read or write data/paper/cache/")
    a = p.parse_args(argv)
    if a.end < a.start or (a.split and not a.start < a.split <= a.end):
        raise SystemExit("need start <= end, and start < split <= end")

    try:
        cfg = with_overrides(load_config(), _pairs(a.set, "--set"), strict=True)
        grid = {k: _parse_value(v) for k, v in _pairs(a.grid, "--grid").items()}
        for k in grid:
            with_overrides(cfg, {k: grid[k][0]}, strict=True)
    except KeyError as exc:
        raise SystemExit(f"unknown setting {exc}")

    client = ThrottledClient(_login(a.token), a.per_minute)
    md: MarketData = BreezeMarket(client, cfg.symbol)
    if not a.no_cache:
        md = CachedMarket(md, symbol=cfg.symbol)

    def progress(i, n, what):
        print(f"\r{i}/{n} {what}  ({client.calls} Breeze calls)", end="", file=sys.stderr, flush=True)

    result = execute(md, cfg, a.start, a.end, a.split, grid or None, progress)
    print(file=sys.stderr)
    name = a.name or f"{result['kind']}-{a.start}-{a.end}-{dt.datetime.now():%Y%m%d%H%M%S}"
    path = save_result(name, result)
    print_result(result)
    print(f"\n{client.calls} Breeze calls. Saved {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
