from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from sqlalchemy import text
import json

from ..utils.postgres import get_conn, ensure_tables
from ..utils.response import log_exception
from ..utils.config import settings
from ..services.breeze_service import BreezeService
from ..utils.session import get_breeze



@dataclass
class OHLCBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


def _ensure_breeze() -> Optional[BreezeService]:
    try:
        runtime = get_breeze()
        if runtime is not None:
            return runtime
        # No fallback - user must login first
        log_exception(Exception("No active Breeze session found"), context="historical._ensure_breeze")
    except Exception as exc:
        log_exception(exc, context="historical._ensure_breeze")
    return None


def _parse_breeze_date(dt_str: str) -> Optional[date]:
    try:
        # Breeze historical returns "YYYY-MM-DD HH:MM:SS" in IST
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.date()
    except Exception:
        return None


def _normalize_bar(row: Dict[str, Any]) -> Optional[OHLCBar]:
    ds = row.get("datetime") or row.get("date")
    iso_date = _parse_breeze_date(ds) if isinstance(ds, str) else None
    if not iso_date:
        return None
    try:
        op = float(row.get("open")) if row.get("open") is not None else None
        hi = float(row.get("high")) if row.get("high") is not None else None
        lo = float(row.get("low")) if row.get("low") is not None else None
        cl = float(row.get("close")) if row.get("close") is not None else None
        vol = float(row.get("volume")) if row.get("volume") is not None else None
        if None in (op, hi, lo, cl):
            return None
        return OHLCBar(date=iso_date, open=op, high=hi, low=lo, close=cl, volume=vol)
    except Exception:
        return None


def _select_cached(symbol: str, start_date: date, end_date: date) -> Dict[date, Dict[str, Any]]:
    cached: Dict[date, Dict[str, Any]] = {}
    try:
        with get_conn() as conn:
            if conn is None:
                return cached
            res = conn.execute(
                text(
                    """
                    SELECT date, ohlc FROM historical_data
                    WHERE symbol = :symbol AND date BETWEEN :start AND :end
                    ORDER BY date
                    """
                ),
                {"symbol": symbol.upper(), "start": start_date, "end": end_date},
            )
            for d, js in res:
                try:
                    cached[d] = js if isinstance(js, dict) else js
                except Exception:
                    continue
    except Exception as exc:
        log_exception(exc, context="historical.select_cached", symbol=symbol)
    return cached


def _insert_rows(symbol: str, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    inserted = 0
    try:
        ensure_tables()
        with get_conn() as conn:
            if conn is None:
                return 0
            for row in rows:
                d = row.get("date")
                if isinstance(d, str):
                    try:
                        d = datetime.strptime(d, "%Y-%m-%d").date()
                    except Exception:
                        continue
                if not isinstance(d, date):
                    continue
                conn.execute(
                    text(
                        """
                        INSERT INTO historical_data (symbol, date, ohlc)
                        VALUES (:symbol, :date, CAST(:ohlc AS JSONB))
                        ON CONFLICT (symbol, date) DO NOTHING
                        """
                    ),
                    {"symbol": symbol.upper(), "date": d, "ohlc": json.dumps(row)},
                )
                inserted += 1
    except Exception as exc:
        log_exception(exc, context="historical.insert_rows", symbol=symbol)
    return inserted


def get_ohlc_daily(symbol: str, start_date: date, end_date: date) -> List[OHLCBar]:
    """Return daily OHLC bars between dates (inclusive), using DB cache or Breeze fallback.

    Caches new rows in the historical_data table for reuse.
    """
    symbol_u = (symbol or "").upper()
    if not symbol_u:
        return []

    cached = _select_cached(symbol_u, start_date, end_date)
    missing_dates: List[date] = []
    dt = start_date
    while dt <= end_date:
        if dt not in cached:
            missing_dates.append(dt)
        dt = date.fromordinal(dt.toordinal() + 1)

    fetched_rows: List[Dict[str, Any]] = []
    if missing_dates:
        breeze = _ensure_breeze()
        if breeze is None:
            # cannot fetch new data; return whatever cached
            pass
        else:
            try:
                resp = breeze.client.get_historical_data_v2(
                    interval="1day",
                    from_date=f"{start_date.isoformat()}T00:00:00.000Z",
                    to_date=f"{end_date.isoformat()}T23:59:59.000Z",
                    stock_code=symbol_u,
                    exchange_code="NSE",
                    product_type="cash",
                )
                success = resp.get("Success") or []
                for r in success:
                    bar = _normalize_bar(r)
                    if not bar:
                        continue
                    fetched_rows.append({
                        "date": bar.date.isoformat(),
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    })
            except Exception as exc:
                log_exception(exc, context="historical.fetch_breeze", symbol=symbol_u)

    if fetched_rows:
        _insert_rows(symbol_u, fetched_rows)
        # merge into cached
        for r in fetched_rows:
            try:
                d = datetime.strptime(r["date"], "%Y-%m-%d").date()
                cached[d] = r
            except Exception:
                continue

    # Build ordered list
    bars: List[OHLCBar] = []
    dt = start_date
    while dt <= end_date:
        row = cached.get(dt)
        if isinstance(row, dict):
            try:
                bars.append(OHLCBar(
                    date=dt,
                    open=float(row.get("open")),
                    high=float(row.get("high")),
                    low=float(row.get("low")),
                    close=float(row.get("close")),
                    volume=float(row.get("volume")) if row.get("volume") is not None else None,
                ))
            except Exception:
                pass
        dt = date.fromordinal(dt.toordinal() + 1)

    return bars


