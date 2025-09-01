from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from ..utils.response import success_response, error_response
from ..utils.usage import get_breeze_usage_summary
from ..services.holidays_service import list_holidays, list_holiday_objects, seed_holidays_from_csv
from ..services.breeze_service import BreezeService
from ..utils.session import get_breeze
from ..utils.config import settings
from ..utils.response import log_exception

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/instruments/status")
def instruments_status() -> Dict[str, Any]:
    """Return static list of indices supported for streaming (MVP)."""

    indices: List[Dict[str, str]] = [
        {
            "display_name": "NIFTY 50",
            "stock_code": "NIFTY",
            "exchange_code": "NSE",
            "product_type": "cash",
        }
    ]
    return {
        "indices": indices,
        "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(),
        "source": "MVP-static",
    }


@router.get("/nifty50/stocks/raw")
def nifty50_equity_list_raw() -> Dict[str, Any]:
    """Fetch Nifty 50 stocks using nselib.capital_market.nifty50_equity_list."""
    try:
        from nselib.capital_market import nifty50_equity_list as get_nifty50
        
        # Fetch nifty 50 stocks
        nifty50_df = get_nifty50()
        
        # Convert DataFrame to list of dictionaries
        stocks = []
        for _, row in nifty50_df.iterrows():
            stocks.append({
                "symbol": row.get('Symbol', ''),
                "name": row.get('Company Name', ''),
                "isin": row.get('ISIN', ''),
                "weight": row.get('Weight(%)', 0),
                "sector": row.get('Sector', '')
            })
        
        return success_response("Nifty 50 stocks (raw)", stocks=stocks, count=len(stocks))
    except ImportError:
        return error_response("nselib library not installed. Please install it with: pip install nselib")
    except Exception as exc:
        log_exception(exc, context="home.nifty50_equity_list")
        return error_response("Failed to fetch Nifty 50 stocks", error=str(exc))


@router.get("/market/status")
def market_status() -> Dict[str, Any]:
    """Advisory market status using a simple NSE hours heuristic (Mon–Fri, 09:15–15:30 IST)."""

    now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))

    is_weekday = ist.weekday() < 5  # 0=Mon .. 4=Fri
    open_time = time(hour=9, minute=15)
    close_time = time(hour=15, minute=30)

    is_open = is_weekday and (open_time <= ist.time() < close_time)

    return {
        "exchange": "NSE",
        "open": bool(is_open),
        "server_time": now_utc.isoformat(),
    }


@router.get("/market/holidays")
def list_market_holidays() -> Dict[str, Any]:
    # Seed from CSV (idempotent): will backfill names if missing
    seed_holidays_from_csv()
    
    # Return all holidays as a simple list of date strings
    holidays = list_holiday_objects()
    # holidays is a list of dicts: {"date": "YYYY-MM-DD", "name": str}
    dates = [str(h.get("date")) for h in holidays if h.get("date")]
    
    return {
        "dates": dates,
        "items": holidays,
        "count": len(dates),
        "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(),
    }


@router.get("/usage")
def usage_summary() -> Dict[str, Any]:
    """Return Breeze API usage summary."""
    return get_breeze_usage_summary()