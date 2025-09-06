from __future__ import annotations

from pathlib import Path

from loguru import logger

from .postgres import ensure_tables
from .instruments_first_run import populate_instruments_from_security_master


def run_daily_refresh_if_needed(root_dir: Path | None = None) -> None:
	"""Perform instruments refresh.

	This function can be called multiple times safely as the underlying operations are idempotent.
	"""
	try:
		ensure_tables()

		root = (root_dir or (Path.cwd() / "SecurityMaster")).resolve()
		# 1) Instruments upsert from SecurityMaster
		try:
			written = populate_instruments_from_security_master(root)
			logger.info("Daily refresh: instruments upserted {} rows", written)
		except Exception as exc:
			logger.exception("Daily refresh instruments failed: {}", exc)



		logger.info("Daily refresh completed successfully")
	except Exception as exc:
		logger.exception("Daily refresh encountered an error: {}", exc)
