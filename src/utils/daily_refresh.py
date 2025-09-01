from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import text

from .postgres import get_conn, ensure_tables
from .instruments_first_run import populate_instruments_from_security_master
from .nifty50_service import refresh_nifty50_list
from ..services.holidays_service import seed_holidays_from_csv
from .usage import record_breeze_call


_MARKER_METHOD = "daily_refresh"


def _already_done_today() -> bool:
	try:
		ensure_tables()
		with get_conn() as conn:
			if conn is None:
				return False
			today = datetime.now(timezone.utc).date().isoformat()
			row = conn.execute(
				text("SELECT 1 FROM api_usage WHERE date = :d AND method = :m"),
				{"d": today, "m": _MARKER_METHOD},
			).fetchone()
			return row is not None
	except Exception:
		return False


def run_daily_refresh_if_needed(root_dir: Path | None = None) -> None:
	"""Perform instruments, Nifty50, and holidays refresh once per UTC day.

	Safe to call repeatedly; it will no-op if today's refresh marker exists.
	"""
	try:
		if _already_done_today():
			logger.info("Daily refresh already completed today; skipping")
			return

		ensure_tables()

		root = (root_dir or (Path.cwd() / "SecurityMaster")).resolve()
		# 1) Instruments upsert from SecurityMaster
		try:
			written = populate_instruments_from_security_master(root)
			logger.info("Daily refresh: instruments upserted {} rows", written)
		except Exception as exc:
			logger.exception("Daily refresh instruments failed: {}", exc)

		# 2) Refresh Nifty50 list
		try:
			n = refresh_nifty50_list()
			logger.info("Daily refresh: nifty50_list updated {} rows", n)
		except Exception as exc:
			logger.exception("Daily refresh nifty50 failed: {}", exc)

		# 3) Seed/refresh holidays from CSV (idempotent)
		try:
			added = seed_holidays_from_csv()
			logger.info("Daily refresh: holidays seeded/updated {} rows", added)
		except Exception as exc:
			logger.exception("Daily refresh holidays failed: {}", exc)

		# 4) Mark done for today
		try:
			record_breeze_call(_MARKER_METHOD)
		except Exception:
			pass
	except Exception as exc:
		logger.exception("Daily refresh encountered an error: {}", exc)
