"""/api/paper/* - read the paper record, or advance it now. Read endpoints never need a Breeze session."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from fastapi import APIRouter

from ..utils.response import error_response, success_response
from ..utils.session import get_breeze
from . import ledger as L
from .config import load_config
from .market import BreezeMarket

router = APIRouter(prefix="/api/paper", tags=["paper"])


def _ledger_or_error():
    ledger = L.load()
    if ledger is None:
        return None, error_response("No paper record yet - log in to Breeze and POST /api/paper/step")
    return ledger, None


@router.get("/summary")
def paper_summary() -> Dict[str, Any]:
    ledger, err = _ledger_or_error()
    return err or success_response("Paper summary", **L.summary(ledger))


@router.get("/trades")
def paper_trades(since: Optional[dt.date] = None) -> Dict[str, Any]:
    ledger, err = _ledger_or_error()
    return err or success_response("Paper trades", trades=L.trades(ledger, since))


@router.get("/equity")
def paper_equity() -> Dict[str, Any]:
    ledger, err = _ledger_or_error()
    if err:
        return err
    return success_response("Paper equity", equity=[{"date": d, "value": v, "benchmark": b} for d, v, b in ledger["equity"]])


@router.get("/replay/{trade_id}")
def paper_replay(trade_id: str) -> Dict[str, Any]:
    """Minute-by-minute data for animating one trade: option bars, Nifty 5-min closes, RSI."""
    data = L.load_replay(trade_id)
    return success_response("Replay", **data) if data else error_response(f"No replay for {trade_id}")


@router.get("/probe")
def paper_probe(day: dt.date, start: str = "09:35", end: str = "09:40", interval: str = "1second",
                expiry: Optional[dt.date] = None, strike: Optional[int] = None, right: str = "call") -> Dict[str, Any]:
    """Read-only check of what Breeze history returns for a short window (option if strike given, else NIFTY)."""
    breeze = get_breeze()
    if breeze is None:
        return error_response("No Breeze session - log in first")
    kw = dict(interval=interval, from_date=f"{day}T{start}:00.000Z", to_date=f"{day}T{end}:00.000Z", stock_code="NIFTY")
    if strike:
        kw.update(exchange_code="NFO", product_type="options", expiry_date=f"{expiry}T06:00:00.000Z",
                  right=right, strike_price=str(strike))
    else:
        kw.update(exchange_code="NSE", product_type="cash")
    try:
        resp = breeze.client.get_historical_data_v2(**kw)
    except Exception as exc:
        return error_response("Breeze call failed", error=str(exc))
    rows = (resp or {}).get("Success") or []
    return success_response("Probe", rows=len(rows), status=(resp or {}).get("Status"), error=(resp or {}).get("Error"),
                            first=rows[:3], last=rows[-2:])


@router.post("/step")
def paper_step() -> Dict[str, Any]:
    breeze = get_breeze()
    if breeze is None:
        return error_response("No Breeze session - log in first")
    try:
        ledger = L.run_step(BreezeMarket(breeze.client, load_config().symbol))
    except Exception as exc:
        return error_response("Paper step failed", error=str(exc))
    return success_response("Paper record updated", **L.summary(ledger))
