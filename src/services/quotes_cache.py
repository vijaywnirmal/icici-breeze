from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..utils.supabase_client import get_supabase
from ..utils.response import log_exception


TABLE = "quotes_cache"


def upsert_quote(symbol: str, payload: Dict[str, Any]) -> None:
	"""Upsert a cached quote for a symbol.

	Expected columns in Supabase table `quotes_cache`:
	- symbol (text, primary key or unique)
	- data (jsonb)
	- updated_at (timestamptz)
	"""
	client = get_supabase()
	if not client:
		return
	try:
		row = {
			"symbol": symbol.upper(),
			"data": payload,
			"updated_at": datetime.utcnow().isoformat() + "Z",
		}
		client.table(TABLE).upsert(row, on_conflict="symbol").execute()
	except Exception as exc:
		log_exception(exc, context="quotes_cache.upsert_quote", symbol=symbol)


def get_cached_quote(symbol: str) -> Optional[Dict[str, Any]]:
	client = get_supabase()
	if not client:
		return None
	try:
		resp = client.table(TABLE).select("data").eq("symbol", symbol.upper()).limit(1).execute()
		if resp and getattr(resp, "data", None):
			row = resp.data[0]
			return row.get("data")
		return None
	except Exception as exc:
		log_exception(exc, context="quotes_cache.get_cached_quote", symbol=symbol)
		return None


