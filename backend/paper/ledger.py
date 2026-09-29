"""Persistence (data/paper/ledger.json, data/paper/replays/<trade id>.json) and the read helpers the API serves."""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
from typing import Optional

from .config import DATA_DIR, load_config
from .engine import contract_label, step
from .market import MarketData

LEDGER = DATA_DIR / "ledger.json"
REPLAYS = DATA_DIR / "replays"
_LOCK = threading.Lock()  # the background runner and POST /api/paper/step can overlap
_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-\d+$")


def load() -> Optional[dict]:
    try:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return ledger if ledger.get("version") == 2 else None  # v1 was the retired daily engine


def _write(path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


def save(ledger: dict) -> None:
    _write(LEDGER, ledger)


def save_replay(trade_id: str, payload: dict) -> None:
    _write(REPLAYS / f"{trade_id}.json", payload)


def load_replay(trade_id: str) -> Optional[dict]:
    if not _ID.match(trade_id):
        return None
    try:
        return json.loads((REPLAYS / f"{trade_id}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_step(md: MarketData, now: Optional[dt.datetime] = None) -> dict:
    with _LOCK:
        ledger = step(md, load_config(), load(), now, save_replay)
        save(ledger)
        return ledger


def summary(ledger: dict) -> dict:
    eq = ledger["equity"]
    cap = ledger["config"]["capital"]
    value = eq[-1][1] if eq else cap
    bench = eq[-1][2] if eq else cap
    peak, worst = cap, 0.0
    for _, v, _ in eq:
        peak = max(peak, v)
        worst = min(worst, (v / peak - 1) * 100)
    trades = ledger["trades"]
    return {
        "start": ledger["start"],
        "last_processed": ledger["last_processed"],
        "sessions": len(eq),
        "capital": cap,
        "value": value,
        "return_pct": round((value / cap - 1) * 100, 2),
        "benchmark_return_pct": round((bench / cap - 1) * 100, 2),
        "max_drawdown_pct": round(worst, 2),
        "trades": len(trades),
        "winning_trades": sum(t["pnl"] > 0 for t in trades),
        "by_exit": {k: sum(t["exit_reason"] == k for t in trades) for k in ("target", "stop", "time")},
        "realized_pnl": round(sum(t["pnl"] for t in trades), 2),
        "charges_paid": round(sum(t["charges"] for t in trades), 2),
        "config": ledger["config"],
        "notes": ledger["notes"][-10:],
    }


def trades(ledger: dict, since: Optional[dt.date] = None) -> list[dict]:
    rows = [t for t in ledger["trades"] if since is None or dt.date.fromisoformat(t["date"]) >= since]
    return [{**t, "label": contract_label(t)} for t in rows]
