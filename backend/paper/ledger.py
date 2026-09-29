"""Persistence (data/paper/ledger.json) and the read helpers the API serves."""
from __future__ import annotations

import datetime as dt
import json
import threading
from typing import Optional

from .config import DATA_DIR, load_config
from .engine import contract_label, step
from .market import MarketData

LEDGER = DATA_DIR / "ledger.json"
_LOCK = threading.Lock()  # the background runner and POST /api/paper/step can overlap


def load() -> Optional[dict]:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save(ledger: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    tmp.replace(LEDGER)


def run_step(md: MarketData, now: Optional[dt.datetime] = None) -> dict:
    with _LOCK:
        ledger = step(md, load_config(), load(), now)
        save(ledger)
        return ledger


def summary(ledger: dict) -> dict:
    eq = ledger["equity"]
    cap = ledger["config"]["capital"]
    value, bench = eq[-1][1], eq[-1][2]
    peak, worst = cap, 0.0
    for _, v, _ in eq:
        peak = max(peak, v)
        worst = min(worst, (v / peak - 1) * 100)
    closes = [t for t in ledger["trades"] if t["action"] == "close"]
    pos = ledger["position"]
    open_pos = None
    if pos:
        unreal = pos["mark"] * pos["qty"] - pos["entry_cost"]
        open_pos = {**pos, "label": contract_label(pos), "unrealized_pnl": round(unreal, 2),
                    "unrealized_pct": round(unreal / pos["entry_cost"] * 100, 2)}
    return {
        "start": ledger["start"],
        "last_processed": ledger["last_processed"],
        "sessions": len(eq) - 1,
        "capital": cap,
        "value": value,
        "return_pct": round((value / cap - 1) * 100, 2),
        "benchmark_return_pct": round((bench / cap - 1) * 100, 2),
        "max_drawdown_pct": round(worst, 2),
        "round_trips": len(closes),
        "winning_trips": sum(t["pnl"] > 0 for t in closes),
        "realized_pnl": round(sum(t["pnl"] for t in closes), 2),
        "charges_paid": round(sum(t["charges"] for t in ledger["trades"]), 2),
        "position": open_pos,
        "pending": ledger["pending"],  # the next-open decision; for the owner's UI, not for publishing
        "config": ledger["config"],
    }


def trades(ledger: dict, since: Optional[dt.date] = None) -> list[dict]:
    rows = [t for t in ledger["trades"] if since is None or dt.date.fromisoformat(t["date"]) >= since]
    return [{**t, "label": contract_label(t)} for t in rows]
