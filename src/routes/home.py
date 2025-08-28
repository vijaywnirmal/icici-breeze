from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter

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
