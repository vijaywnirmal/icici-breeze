from __future__ import annotations

from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field


class WatchItem(BaseModel):
	"""Represents a single instrument on the user's watchlist."""
	symbol: str = Field(..., min_length=1)
	exchange_code: Literal['NSE', 'NFO', 'BSE'] = 'NSE'
	product_type: Literal['cash', 'futures', 'options'] = 'cash'
	display_name: Optional[str] = None
	# Cached quote fields for UI tiles (optional, best-effort)
	last_quote: Optional[Dict[str, Any]] = None
	# Minimal alert-ready configuration (stored only; delivery not implemented)
	alert_up_pct: Optional[float] = None
	alert_down_pct: Optional[float] = None


class Watchlist(BaseModel):
	"""Represents the user's watchlist with a name and ordered items."""
	name: str = 'My Watchlist'
	items: List[WatchItem] = Field(default_factory=list)
