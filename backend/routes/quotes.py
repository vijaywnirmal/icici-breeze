from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from ..utils.response import log_exception
from ..services.quotes_cache import get_cached_quote, delete_quote



router = APIRouter(prefix="/api", tags=["quotes"])


def _utc_now_iso() -> str:
    """Return current UTC time in RFC 3339 format with Z suffix."""
    return datetime.now(tz=ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")


def _now_ist(now_utc: Optional[datetime] = None) -> datetime:
    now_utc = now_utc or datetime.now(tz=ZoneInfo("UTC"))
    return now_utc.astimezone(ZoneInfo("Asia/Kolkata"))


def _is_market_open_ist(now_utc: Optional[datetime] = None) -> bool:
    ist = _now_ist(now_utc)
    # Skip weekends and holidays using NSE calendar
    if ist.weekday() >= 5:
        return False
    # Only check for weekends, holiday checking removed
    open_time = time(hour=9, minute=15)
    close_time = time(hour=15, minute=30)
    return open_time <= ist.time() < close_time


def _is_reset_window_ist(now_utc: Optional[datetime] = None) -> bool:
    """Return True during 09:00–09:15 IST on weekdays.

    During this window we "lose" previous close values from cache to avoid
    displaying stale prices right before market open.
    """
    ist = _now_ist(now_utc)
    # Only reset on weekdays (holiday checking removed)
    if ist.weekday() >= 5:
        return False
    reset_start = time(hour=9, minute=0)
    reset_end = time(hour=9, minute=15)
    return reset_start <= ist.time() < reset_end


def _last_session_close_range_utc(now_utc: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """Return a tight window around the official close minute (15:30 IST).

    We fetch 15:20–15:31 IST to ensure the 15:30 bar is included and select
    the 15:30:00 bar explicitly.
    """
    ist = _now_ist(now_utc)
    session_date = ist.date()
    open_probe = time(15, 20)
    close_time = time(15, 30)

    if ist.weekday() >= 5:
        shift = ist.weekday() - 4
        session_date = (ist - timedelta(days=shift)).date()
    elif ist.time() < time(9, 15):
        prev = ist - timedelta(days=1)
        while prev.weekday() >= 5:
            prev -= timedelta(days=1)
        session_date = prev.date()

    from_ist = datetime.combine(session_date, open_probe, tzinfo=ZoneInfo("Asia/Kolkata"))
    to_ist = datetime.combine(session_date, close_time, tzinfo=ZoneInfo("Asia/Kolkata")) + timedelta(minutes=1)
    return from_ist.astimezone(ZoneInfo("UTC")), to_ist.astimezone(ZoneInfo("UTC"))








def _previous_weekday(date_ist: datetime) -> datetime:
    """Return a datetime set to previous weekday (skipping Sat/Sun), preserving tzinfo."""
    prev = date_ist - timedelta(days=1)
    while prev.weekday() >= 5:  # 5=Sat, 6=Sun
        prev -= timedelta(days=1)
    return prev





@router.get("/quotes/index")
def get_index_quote(
    symbol: str = Query(..., description="Index code, e.g., NIFTY or BSESEN"),
    exchange: str = Query("NSE", description="Exchange code, e.g., NSE or BSE"),
) -> Dict[str, Any]:
    """Get cached quote data from WebSocket cache only."""
    symbol_upper = (symbol or "").upper()
    is_open = _is_market_open_ist()
    in_reset = _is_reset_window_ist()

    payload: Dict[str, Any] = {
        "symbol": symbol_upper,
        "status": "live" if is_open else "closed",
        "ltp": None,
        "close": None,
        "change_pct": None,
        "bid": None,
        "ask": None,
        "timestamp": _utc_now_iso(),
        "reset": in_reset,
    }

    # Between 09:00–09:15 IST, clear any cached close and return empty values
    if in_reset:
        try:
            delete_quote(symbol_upper)
        except Exception as exc:
            log_exception(exc, context="quotes.get_index_quote.cache_delete", symbol=symbol_upper)
        return payload

    # Always return cached data only (from WebSocket cache)
    cached = get_cached_quote(symbol_upper)
    if isinstance(cached, dict):
        payload.update(cached)
    
    return payload
