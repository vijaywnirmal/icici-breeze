from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query

from ..utils.config import settings
from ..services.breeze_service import BreezeService
from ..utils.session import get_breeze
from ..utils.response import log_exception
from ..services.quotes_cache import get_cached_quote, upsert_quote, delete_quote
from ..utils.usage import record_breeze_call


router = APIRouter(prefix="/api", tags=["quotes"])

_BREEZE: Optional[BreezeService] = None


def _utc_now_iso() -> str:
    """Return current UTC time in RFC 3339 format with Z suffix."""
    return datetime.now(tz=ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")


def _now_ist(now_utc: Optional[datetime] = None) -> datetime:
    now_utc = now_utc or datetime.now(tz=ZoneInfo("UTC"))
    return now_utc.astimezone(ZoneInfo("Asia/Kolkata"))


def _is_market_open_ist(now_utc: Optional[datetime] = None) -> bool:
    ist = _now_ist(now_utc)
    # Skip weekends and holidays from CSV
    if ist.weekday() >= 5:
        return False
    iso_date = ist.date().isoformat()
    try:
        from ..utils.holidays_csv import load_holidays
        holidays = load_holidays()
    except Exception:
        holidays = set()
    if iso_date in holidays or iso_date in settings.market_holidays:
        return False
    open_time = time(hour=9, minute=15)
    close_time = time(hour=15, minute=30)
    return open_time <= ist.time() < close_time


def _is_reset_window_ist(now_utc: Optional[datetime] = None) -> bool:
    """Return True during 09:00–09:15 IST on weekdays.

    During this window we "lose" previous close values from cache to avoid
    displaying stale prices right before market open.
    """
    ist = _now_ist(now_utc)
    # Only reset on active trading days (not weekends/holidays)
    if ist.weekday() >= 5:
        return False
    try:
        from ..utils.holidays_csv import load_holidays
        holidays = load_holidays()
    except Exception:
        holidays = set()
    if ist.date().isoformat() in holidays or ist.date().isoformat() in settings.market_holidays:
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


def _to_breeze_iso(dt_utc: datetime) -> str:
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _ensure_breeze() -> Optional[BreezeService]:
    global _BREEZE
    if _BREEZE is not None:
        return _BREEZE
    try:
        # Prefer runtime session from login; else fall back to ENV one
        runtime = get_breeze()
        if runtime is not None:
            _BREEZE = runtime
            return _BREEZE
        if settings.breeze_api_key and settings.breeze_api_secret and settings.breeze_session_token:
            service = BreezeService(api_key=settings.breeze_api_key)
            result = service.login_and_fetch_profile(
                api_secret=settings.breeze_api_secret,
                session_key=settings.breeze_session_token,
            )
            if result.success:
                _BREEZE = service
                return _BREEZE
            else:
                log_exception(Exception(result.error or "login failed"), context="quotes._ensure_breeze")
    except Exception as exc:
        log_exception(exc, context="quotes._ensure_breeze")
    return None


def _normalize_quote(symbol: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    ltp = raw.get("last") or raw.get("ltp") or raw.get("close") or raw.get("open")
    close_px = raw.get("close")
    bid = raw.get("bPrice") or raw.get("best_bid_price")
    ask = raw.get("sPrice") or raw.get("best_ask_price")
    change_pct = raw.get("change") or raw.get("pChange")
    ts = raw.get("ltt") or raw.get("datetime") or raw.get("timestamp")
    return {
        "symbol": symbol,
        "ltp": ltp,
        "close": close_px,
        "change_pct": change_pct,
        "bid": bid,
        "ask": ask,
        "timestamp": ts or _utc_now_iso(),
    }


def _previous_weekday(date_ist: datetime) -> datetime:
    """Return a datetime set to previous weekday (skipping Sat/Sun), preserving tzinfo."""
    prev = date_ist - timedelta(days=1)
    while prev.weekday() >= 5:  # 5=Sat, 6=Sun
        prev -= timedelta(days=1)
    return prev


def _last_daily_range_utc(now_utc: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """IST daily window: 00:00:01 → 23:59:59 for last trading day.

    If current IST time is before 15:30 (or any time before official close), use
    the previous weekday as the last trading day; otherwise, use today.
    """
    ist_now = _now_ist(now_utc)
    close_time = time(15, 30)

    target_date = ist_now.date()
    if ist_now.time() < close_time:
        target_dt = _previous_weekday(datetime.combine(target_date, time(12, 0), tzinfo=ZoneInfo("Asia/Kolkata")))
        target_date = target_dt.date()

    start_ist = datetime.combine(target_date, time(0, 0, 1), tzinfo=ZoneInfo("Asia/Kolkata"))
    end_ist = datetime.combine(target_date, time(23, 59, 59), tzinfo=ZoneInfo("Asia/Kolkata"))
    return start_ist.astimezone(ZoneInfo("UTC")), end_ist.astimezone(ZoneInfo("UTC"))


@router.get("/quotes/index")
def get_index_quote(
    symbol: str = Query(..., description="Index code, e.g., NIFTY or BSESEN"),
    exchange: str = Query("NSE", description="Exchange code, e.g., NSE or BSE"),
) -> Dict[str, Any]:
    symbol_upper = (symbol or "").upper()
    exchange_upper = (exchange or "NSE").upper()
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
        # No further data population during reset window
        return payload

    if not is_open:
        # Cache-first: avoid Breeze calls if we have a cached snapshot for closed market
        cached = get_cached_quote(symbol_upper)
        if isinstance(cached, dict):
            payload.update(cached)
            return payload
        try:
            breeze = _ensure_breeze()
            if breeze:
                try:
                    # Use 1day interval for last daily close as requested
                    f_utc, t_utc = _last_daily_range_utc()
                    record_breeze_call("get_historical_data_v2")
                    resp = breeze.client.get_historical_data_v2(
                        interval="1day",
                        from_date=_to_breeze_iso(f_utc),
                        to_date=_to_breeze_iso(t_utc),
                        stock_code=symbol_upper,
                        exchange_code=exchange_upper,
                        product_type="cash",
                    )
                    if isinstance(resp, dict):
                        success = resp.get("Success") or []
                        if isinstance(success, list) and success:
                            # For 1day, take the last daily bar
                            last = success[-1]
                            close_px = last.get("close")
                            if isinstance(close_px, (int, float)):
                                close_px = round(float(close_px), 2)
                            if close_px is not None:
                                payload.update({
                                    "ltp": close_px,
                                    "close": close_px,
                                    "timestamp": last.get("datetime") or payload["timestamp"],
                                })
                                try:
                                    upsert_quote(symbol_upper, payload)
                                except Exception as exc:
                                    log_exception(exc, context="quotes.get_index_quote.cache_upsert", symbol=symbol_upper)
                        elif resp.get("Error"):
                            log_exception(Exception(resp["Error"]), context="quotes.get_index_quote.historical_v2")
                except Exception as exc:
                    log_exception(exc, context="quotes.get_index_quote.historical_v2", symbol=symbol_upper)

                if payload.get("close") is None:
                    try:
                        record_breeze_call("get_quotes")
                        quote = breeze.client.get_quotes(
                            stock_code=symbol_upper,
                            exchange_code=exchange_upper,
                            product_type="cash",
                        )
                        if isinstance(quote, dict):
                            payload.update(_normalize_quote(symbol_upper, quote))
                            try:
                                upsert_quote(symbol_upper, payload)
                            except Exception as exc:
                                log_exception(exc, context="quotes.get_index_quote.cache_upsert", symbol=symbol_upper)
                    except Exception as exc:
                        log_exception(exc, context="quotes.get_index_quote.get_quotes_fallback", symbol=symbol_upper)
            else:
                cached = get_cached_quote(symbol_upper)
                if isinstance(cached, dict):
                    payload.update(cached)
        except Exception as exc:
            log_exception(exc, context="quotes.get_index_quote.get_quotes", symbol=symbol_upper)
            cached = get_cached_quote(symbol_upper)
            if isinstance(cached, dict):
                payload.update(cached)

    return payload
