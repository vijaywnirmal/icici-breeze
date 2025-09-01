from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query
from sqlalchemy import text

from ..utils.postgres import get_conn
from ..utils.response import error_response, success_response, log_exception
from ..services.quotes_cache import get_cached_quote, upsert_quote
from .quotes import _is_market_open_ist, _last_session_close_range_utc, _to_breeze_iso


router = APIRouter(prefix="/api", tags=["nifty"])


def _normalize_symbol(val: Any) -> str:
    try:
        s = str(val or "").strip().upper()
        # Some feeds include ".NS" suffix
        if s.endswith(".NS"):
            s = s[:-3]
        return s
    except Exception:
        return ""


def _fetch_nifty50_symbols() -> List[Dict[str, str]]:
    # Try multiple nselib entry points to be robust across versions
    df = None
    try:
        from nselib.nse import nifty50_stock_list as get_list  # type: ignore
        df = get_list()
    except Exception:
        try:
            from nselib.capital_market import nifty50_equity_list as get_list_alt  # type: ignore
            df = get_list_alt()
        except Exception as exc:
            log_exception(exc, context="nifty.fetch_symbols.import")
            return []

    try:
        cols = {str(c).lower(): c for c in df.columns}
        sym_col = cols.get('symbol') or cols.get('symbol_name') or list(cols.values())[0]
        # Common name columns across variants
        name_col = cols.get('company name') or cols.get('company') or cols.get('name') or cols.get('companyname') or sym_col
        items: List[Dict[str, str]] = []
        for _, row in df.iterrows():
            sym = _normalize_symbol(row.get(sym_col))
            name = str(row.get(name_col) or sym)
            if sym:
                items.append({"symbol": sym, "company_name": name})
        return items
    except Exception as exc:
        log_exception(exc, context="nifty.fetch_symbols.parse")
        return []


def _try_fetch_close(breeze, code: str) -> Optional[float]:
    from ..utils.usage import record_breeze_call
    try:
        # Prefer last session 15:30 minute close when market is closed
        if not _is_market_open_ist():
            try:
                f_utc, t_utc = _last_session_close_range_utc()
                record_breeze_call("get_historical_data_v2")
                r2 = breeze.client.get_historical_data_v2(
                    interval="1minute",
                    from_date=_to_breeze_iso(f_utc),
                    to_date=_to_breeze_iso(t_utc),
                    stock_code=code,
                    exchange_code="NSE",
                    product_type="cash",
                )
                if isinstance(r2, dict):
                    s2 = r2.get("Success") or []
                    if isinstance(s2, list) and s2:
                        last_bar = s2[-1]
                        c2 = last_bar.get("close")
                        if isinstance(c2, (int, float)):
                            return round(float(c2), 2)
            except Exception:
                pass

        # Fallback: Historical daily close
        from .quotes import _last_daily_range_utc
        f_utc, t_utc = _last_daily_range_utc()
        record_breeze_call("get_historical_data_v2")
        resp = breeze.client.get_historical_data_v2(
            interval="1day",
            from_date=_to_breeze_iso(f_utc),
            to_date=_to_breeze_iso(t_utc),
            stock_code=code,
            exchange_code="NSE",
            product_type="cash",
        )
        if isinstance(resp, dict):
            rows = resp.get("Success") or []
            if isinstance(rows, list) and rows:
                last = rows[-1]
                close_px = last.get("close")
                if isinstance(close_px, (int, float)):
                    return round(float(close_px), 2)
        # 2) Fallback to live quote
        record_breeze_call("get_quotes")
        q = breeze.client.get_quotes(stock_code=code, exchange_code="NSE", product_type="cash")
        if isinstance(q, dict):
            last_px = q.get("last") or q.get("ltp") or q.get("close")
            if isinstance(last_px, (int, float)):
                return round(float(last_px), 2)
    except Exception:
        return None
    return None


def _get_last_close_with_candidates(codes: List[str]) -> Tuple[Optional[float], Optional[str]]:
    try:
        # Cache-first per candidate
        for c in codes:
            cached = get_cached_quote(c)
            if isinstance(cached, dict):
                close_px = cached.get("close") or cached.get("ltp")
                if isinstance(close_px, (int, float)):
                    return float(close_px), c

        from .quotes import _ensure_breeze
        breeze = _ensure_breeze()
        if not breeze:
            return None, None
        for c in codes:
            val = _try_fetch_close(breeze, c)
            if isinstance(val, (int, float)):
                try:
                    upsert_quote(c, {"symbol": c, "close": val, "ltp": val})
                except Exception:
                    pass
                return val, c
        return None, None
    except Exception as exc:
        log_exception(exc, context="nifty.get_last_close_candidates")
        return None, None


@router.get("/nifty50/stocks")
def list_nifty50_stocks(api_session: str | None = Query(None)) -> Dict[str, Any]:
    """Return NIFTY 50 constituents from DB with mapped stock_code and last close price."""
    try:
        with get_conn() as conn:
            if conn is None:
                return error_response("Database not configured")
            rows = conn.execute(text("""
                SELECT symbol, stock_code, token, company_name, exchange
                FROM nifty50_list
                WHERE exchange = 'NSE'
                ORDER BY symbol
            """)).fetchall()
            out: List[Dict[str, Any]] = []
            for r in rows:
                symbol = r[0]
                stock_code = (r[1] or symbol).upper()
                token = r[2]
                name = r[3]
                ex = r[4]
                # Build candidate codes: primary stock_code, symbol, plus ".NS" variants
                candidates = [stock_code]
                if symbol and symbol != stock_code:
                    candidates.append(symbol.upper())
                if not stock_code.endswith(".NS"):
                    candidates.append(stock_code + ".NS")
                close_px, used = _get_last_close_with_candidates(candidates)
                out.append({
                    "symbol": symbol,
                    "stock_code": stock_code,
                    "token": token,
                    "company_name": name,
                    "stock_name": name,
                    "exchange": ex,
                    "close": close_px,
                    "_code_used": used,
                })
            return success_response("Nifty 50 stocks", stocks=out)
    except Exception as exc:
        log_exception(exc, context="nifty.list_db")
        return error_response("Failed to list Nifty 50 stocks", error=str(exc))


