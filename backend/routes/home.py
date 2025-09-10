from __future__ import annotations

import pandas as pd
from datetime import datetime, time
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from ..utils.response import success_response, error_response

from ..services.breeze_service import BreezeService
from ..services.holiday_service import get_holidays_for_year, refresh_holidays_2025, load_all_historical_holidays
from ..utils.session import get_breeze
from ..utils.config import settings
from ..utils.response import log_exception

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/instruments/status")
def instruments_status() -> Dict[str, Any]:
    """Return dynamic list of indices supported for streaming."""
    try:
        # Get indices from Breeze service if available
        breeze = get_breeze()
        if breeze and hasattr(breeze, 'get_indices'):
            indices = breeze.get_indices()
        else:
            # Fallback to empty list if no Breeze service
            indices = []
        
        return {
            "indices": indices,
            "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(),
            "source": "breeze_api" if breeze else "no_data",
        }
    except Exception as exc:
        log_exception(exc, context="home.instruments_status")
        return {
            "indices": [],
            "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(),
            "source": "error",
            "error": str(exc)
        }




# Market status endpoint moved to instruments router to avoid conflicts


@router.get("/market/holidays")
def list_market_holidays(
    year: int = Query(2025, description="Year to fetch holidays for")
) -> Dict[str, Any]:
    """Get market holidays for a specific year."""
    try:
        holidays_df = get_holidays_for_year(year)
        
        if len(holidays_df) > 0:
            # Format data for API response
            items = []
            for _, row in holidays_df.iterrows():
                date_str = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], 'strftime') else str(row["date"])
                items.append({
                    "date": date_str,
                    "day": row["day"],
                    "name": row["name"]
                })
            
            return {
                "year": year,
                "items": items,
                "count": len(items),
                "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(),
                "source": "database" if year != 2025 else "nse_api"
            }
        else:
            return {
                "year": year,
                "items": [],
                "count": 0,
                "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(),
                "source": "no_data",
                "message": f"No holidays found for year {year}"
            }
        
    except Exception as exc:
        log_exception(exc, context="home.list_market_holidays")
        return {
            "year": year,
            "items": [],
            "count": 0,
            "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat(),
            "source": "error",
            "error": str(exc)
        }


@router.post("/market/holidays/refresh")
def refresh_holidays() -> Dict[str, Any]:
    """Refresh holidays for 2025 from NSE API."""
    try:
        result = refresh_holidays_2025()
        return {
            "success": result["success"],
            "message": result["message"],
            "count": result["count"],
            "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat()
        }
    except Exception as exc:
        log_exception(exc, context="home.refresh_holidays")
        return {
            "success": False,
            "message": f"Error refreshing holidays: {str(exc)}",
            "count": 0
        }


@router.post("/market/holidays/load-historical")
def load_historical_holidays() -> Dict[str, Any]:
    """Load all historical holidays from CSV data (2011-2025)."""
    try:
        result = load_all_historical_holidays()
        return {
            "success": result["success"],
            "message": result["message"],
            "count": result["count"],
            "last_updated": datetime.utcnow().replace(tzinfo=ZoneInfo("UTC")).isoformat()
        }
    except Exception as exc:
        log_exception(exc, context="home.load_historical_holidays")
        return {
            "success": False,
            "message": f"Error loading historical holidays: {str(exc)}",
            "count": 0
        }




