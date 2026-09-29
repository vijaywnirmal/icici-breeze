"""/api/paper/* - read the paper record, or advance it now. Read endpoints never need a Breeze session."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

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


@router.get("/session")
def paper_session() -> Dict[str, Any]:
    """Is there a live Breeze session? (A session object can outlive its day; get_funds proves it works.)"""
    breeze = get_breeze()
    if breeze is None:
        return success_response("No session", logged_in=False)
    try:
        resp = breeze.client.get_funds() or {}
        ok = resp.get("Status") == 200
    except Exception:
        ok = False
    name = (getattr(breeze, "profile", None) or {}).get("first_name") if ok else None
    return success_response("Session", logged_in=ok, name=name)


@router.get("/login-url")
def paper_login_url() -> Dict[str, Any]:
    """ICICI's login page for this app's API key; after logging in, its redirect carries ?apisession=..."""
    import os
    import urllib.parse
    key = (os.getenv("BREEZE_API_KEY") or "").strip()
    if not key:
        return error_response("BREEZE_API_KEY is not set in icici-breeze/.env")
    return success_response("Login URL", url="https://api.icicidirect.com/apiuser/login?api_key=" + urllib.parse.quote_plus(key))


class _Login(BaseModel):
    session_token: str


@router.post("/login")
def paper_login(body: _Login) -> Dict[str, Any]:
    """Start today's Breeze session from a session token, using the key/secret in .env (never sent by the
    caller), then bring the paper record up to date."""
    import os
    from ..services.breeze_service import BreezeService
    from ..utils.session import set_breeze
    key, secret = (os.getenv("BREEZE_API_KEY") or "").strip(), (os.getenv("BREEZE_API_SECRET") or "").strip()
    token = body.session_token.strip()
    if not key or not secret:
        return error_response("Set BREEZE_API_KEY and BREEZE_API_SECRET in icici-breeze/.env")
    if not token or len(token) > 64:
        return error_response("Paste the apisession value from ICICI's redirect URL")
    service = BreezeService(api_key=key)
    result = service.login_and_fetch_profile(api_secret=secret, session_key=token)
    if not result.success:
        return error_response("Breeze login failed", error=result.error)
    service.profile = result.profile or {}
    set_breeze(service)
    try:
        ledger = L.run_step(BreezeMarket(service.client, load_config().symbol))
        return success_response("Logged in", name=service.profile.get("first_name"), **L.summary(ledger))
    except Exception as exc:
        return success_response("Logged in (paper step failed)", name=service.profile.get("first_name"), step_error=str(exc))


_EDITABLE = {"oversold", "overbought", "first_entry", "last_entry", "max_trades_per_day", "lots", "lot_size",
             "target_pct", "stop_pct", "square_off", "catch_up_missed_days", "slippage_pct"}


@router.get("/config")
def paper_config_get() -> Dict[str, Any]:
    return success_response("Paper config", config=load_config().as_dict(), editable=sorted(_EDITABLE))


@router.put("/config")
def paper_config_put(changes: Dict[str, Any]) -> Dict[str, Any]:
    """Change strategy settings (written to data/paper/config.json; applies from the next session)."""
    import json
    from dataclasses import fields
    from .config import DATA_DIR, PaperConfig
    bad = sorted(set(changes) - _EDITABLE)
    if bad:
        return error_response(f"Not editable: {', '.join(bad)}")
    path = DATA_DIR / "config.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current = {}
    current.update(changes)
    kinds = {f.name: type(getattr(PaperConfig(), f.name)) for f in fields(PaperConfig)}
    try:
        for k, v in changes.items():  # validate before writing
            if kinds[k] is bool:
                continue
            kinds[k](v)
            if k in ("first_entry", "last_entry", "square_off"):
                dt.datetime.strptime(str(v), "%H:%M")
    except (TypeError, ValueError) as exc:
        return error_response("Invalid value", error=str(exc))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return success_response("Saved - applies from the next session", config=load_config().as_dict())


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
