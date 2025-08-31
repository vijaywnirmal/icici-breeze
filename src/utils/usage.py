from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Tuple

from sqlalchemy import text

from .postgres import get_conn, ensure_tables
from .response import log_exception


_WINDOW_SECONDS = 60
_MINUTE_LIMIT = 100
_DAILY_LIMIT = 5000


# In-memory sliding window of recent call timestamps per method
_recent_calls: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=2000))


def _evict_old(dq: Deque[float], now_s: float) -> None:
	cutoff = now_s - _WINDOW_SECONDS
	while dq and dq[0] < cutoff:
		dq.popleft()


def record_breeze_call(method: str) -> None:
	"""Record a Breeze API call for minute window and persist daily count.

	- Updates in-memory 60s window (per method)
	- Upserts today's per-method count in PostgreSQL
	"""
	now_s = time.time()
	try:
		dq = _recent_calls[method]
		_evict_old(dq, now_s)
		dq.append(now_s)
	except Exception:
		pass

	# Persist daily count
	try:
		ensure_tables()
		today = datetime.now(timezone.utc).date().isoformat()
		with get_conn() as conn:
			if conn is None:
				return
			conn.execute(
				text(
					"""
					INSERT INTO api_usage (date, method, count, updated_at)
					VALUES (:date, :method, 1, :now)
					ON CONFLICT (date, method)
					DO UPDATE SET count = api_usage.count + 1, updated_at = EXCLUDED.updated_at
					"""
				),
				{"date": today, "method": method, "now": datetime.now(timezone.utc).isoformat()}
			)
	except Exception as exc:
		log_exception(exc, context="usage.record_breeze_call")


def get_breeze_usage_summary() -> Dict[str, object]:
	"""Return minute-window and today usage summary.

	Returns keys: minute_total, minute_by_method, today_total, today_by_method,
	minute_limit, daily_limit, minute_near_limit, daily_near_limit.
	"""
	now_s = time.time()
	minute_by_method: Dict[str, int] = {}
	for method, dq in _recent_calls.items():
		try:
			_evict_old(dq, now_s)
			minute_by_method[method] = len(dq)
		except Exception:
			minute_by_method[method] = len(dq)
	minute_total = sum(minute_by_method.values())

	# Load today's persisted counts
	today_total = 0
	today_by_method: Dict[str, int] = {}
	try:
		today = datetime.now(timezone.utc).date().isoformat()
		with get_conn() as conn:
			if conn is not None:
				res = conn.execute(text("SELECT method, count FROM api_usage WHERE date = :date"), {"date": today})
				for method, count in res:
					today_by_method[method] = int(count or 0)
					today_total += int(count or 0)
	except Exception as exc:
		log_exception(exc, context="usage.get_breeze_usage_summary")

	return {
		"minute_total": minute_total,
		"minute_by_method": minute_by_method,
		"today_total": today_total,
		"today_by_method": today_by_method,
		"minute_limit": _MINUTE_LIMIT,
		"daily_limit": _DAILY_LIMIT,
		"minute_near_limit": minute_total >= int(_MINUTE_LIMIT * 0.9),
		"daily_near_limit": today_total >= int(_DAILY_LIMIT * 0.96),
	}


