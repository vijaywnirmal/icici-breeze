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
