from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Query

from ..services.historical_service import get_ohlc_daily


router = APIRouter(prefix="/api", tags=["historical"])


@router.get("/historical/daily")
def historical_daily(
	symbol: str = Query(..., description="Symbol, e.g., NIFTY"),
	start_date: date = Query(...),
	end_date: date = Query(...),
) -> Dict[str, Any]:
	bars = get_ohlc_daily(symbol, start_date, end_date)
	items: List[Dict[str, Any]] = [
		{
			"date": b.date.isoformat(),
			"open": b.open,
			"high": b.high,
			"low": b.low,
			"close": b.close,
			"volume": b.volume,
		}
		for b in bars
	]
	return {"symbol": symbol.upper(), "items": items}


