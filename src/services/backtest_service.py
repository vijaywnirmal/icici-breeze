from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from .historical_service import OHLCBar


@dataclass
class Trade:
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    pnl: float
    pnl_pct: float


@dataclass
class BacktestResult:
    trades: List[Trade]
    summary: Dict[str, float]


def _moving_average(values: List[float], window: int) -> List[Optional[float]]:
    if window <= 0:
        return [None] * len(values)
    out: List[Optional[float]] = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out


def run_ma_crossover(bars: List[OHLCBar], fast: int, slow: int, capital: float) -> BacktestResult:
    if not bars or fast <= 0 or slow <= 0 or fast >= slow:
        return BacktestResult(
            trades=[],
            summary={"trades": 0, "net_pnl": 0.0, "return_pct": 0.0, "max_drawdown": 0.0, "final_equity": capital},
        )

    closes = [b.close for b in bars]
    fast_ma = _moving_average(closes, fast)
    slow_ma = _moving_average(closes, slow)

    position_qty = 0.0
    entry_price = 0.0
    entry_dt = None
    trades: List[Trade] = []
    equity = capital
    peak_equity = capital
    max_drawdown = 0.0

    # loop until len-2 so we can use i+1 safely
    for i in range(1, len(bars) - 1):
        f, s = fast_ma[i], slow_ma[i]
        pf, ps = fast_ma[i - 1], slow_ma[i - 1]
        if None in (f, s, pf, ps):
            continue

        cross_up = pf < ps and f >= s
        cross_dn = pf > ps and f <= s

        next_bar = bars[i + 1]  # execute on next day's open

        if position_qty == 0.0 and cross_up:
            entry_price = next_bar.open
            position_qty = equity / entry_price
            entry_dt = next_bar.date

        elif position_qty > 0.0 and cross_dn:
            exit_price = next_bar.open
            pnl = (exit_price - entry_price) * position_qty
            pnl_pct = (exit_price / entry_price - 1.0) * 100.0
            equity += pnl
            trades.append(
                Trade(
                    entry_date=datetime.combine(entry_dt, datetime.min.time()),
                    exit_date=datetime.combine(next_bar.date, datetime.min.time()),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                )
            )
            position_qty = 0.0
            entry_price = 0.0
            entry_dt = None

        # Track drawdown
        if equity > peak_equity:
            peak_equity = equity
        dd = (equity / peak_equity - 1.0) * 100.0
        if dd < max_drawdown:
            max_drawdown = dd

    # Liquidate if still in position
    if position_qty > 0.0 and entry_dt:
        last_bar = bars[-1]
        exit_price = last_bar.close
        pnl = (exit_price - entry_price) * position_qty
        pnl_pct = (exit_price / entry_price - 1.0) * 100.0
        equity += pnl
        trades.append(
            Trade(
                entry_date=datetime.combine(entry_dt, datetime.min.time()),
                exit_date=datetime.combine(last_bar.date, datetime.min.time()),
                entry_price=entry_price,
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
            )
        )

    net_pnl = equity - capital
    return_pct = (equity / capital - 1.0) * 100.0 if capital > 0 else 0.0
    summary = {
        "trades": len(trades),
        "net_pnl": net_pnl,
        "return_pct": return_pct,
        "max_drawdown": max_drawdown,
        "final_equity": equity,
    }

    return BacktestResult(trades=trades, summary=summary)
