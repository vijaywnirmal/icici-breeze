from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
import json

from sqlalchemy import text

from ..utils.postgres import get_conn, ensure_tables
from ..utils.response import log_exception


TABLE = "quotes_cache"


def upsert_quote(symbol: str, payload: Dict[str, Any]) -> None:
	"""Upsert a cached quote for a symbol in PostgreSQL."""
	try:
		ensure_tables()
		with get_conn() as conn:
			if conn is None:
				return
			conn.execute(
				text(
					f"""
					INSERT INTO {TABLE} (symbol, data, updated_at)
					VALUES (:symbol, CAST(:data AS JSONB), :updated_at)
					ON CONFLICT (symbol)
					DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
					"""
				),
				{
					"symbol": symbol.upper(),
					"data": json.dumps(payload),
					"updated_at": datetime.utcnow().isoformat() + "Z",
				},
			)
	except Exception as exc:
		log_exception(exc, context="quotes_cache.upsert_quote", symbol=symbol)


def get_cached_quote(symbol: str) -> Optional[Dict[str, Any]]:
	try:
		with get_conn() as conn:
			if conn is None:
				return None
			res = conn.execute(text(f"SELECT data FROM {TABLE} WHERE symbol = :symbol LIMIT 1"), {"symbol": symbol.upper()})
			row = res.fetchone()
			if not row:
				return None
			data = row[0]
			if isinstance(data, str):
				try:
					return json.loads(data)
				except Exception:
					return None
			return data
	except Exception as exc:
		log_exception(exc, context="quotes_cache.get_cached_quote", symbol=symbol)
		return None


def delete_quote(symbol: str) -> None:
	"""Delete a cached quote row for a symbol from PostgreSQL, if configured."""
	try:
		with get_conn() as conn:
			if conn is None:
				return
			conn.execute(text(f"DELETE FROM {TABLE} WHERE symbol = :symbol"), {"symbol": symbol.upper()})
	except Exception as exc:
		log_exception(exc, context="quotes_cache.delete_quote", symbol=symbol)


