from __future__ import annotations

import asyncio
from datetime import datetime, time, date
from pathlib import Path
from typing import Optional

from loguru import logger

from .instruments_first_run import populate_instruments_from_security_master
from .security_master import download_and_extract_security_master


class DailyInstrumentsUpdater:
    """Runs a daily update between 08:00–08:15 IST to refresh instruments."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = (root_dir or (Path.cwd() / "SecurityMaster")).resolve()
        self._last_run_date: Optional[date] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            try:
                self._task.cancel()
            except Exception:
                pass
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        from zoneinfo import ZoneInfo

        ist = ZoneInfo("Asia/Kolkata")
        window_start = time(8, 0)
        window_end = time(8, 15)

        while self._running:
            try:
                now = datetime.now(tz=ist)
                in_window = window_start <= now.time() <= window_end
                already_ran = self._last_run_date == now.date()
                if in_window and not already_ran:
                    await self._run_once()
                    self._last_run_date = now.date()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.exception("Daily instruments updater encountered error: {}", exc)
            # Check every 5 minutes
            try:
                await asyncio.sleep(300)
            except asyncio.CancelledError:
                return

    async def _run_once(self) -> None:
        logger.info("Running daily instruments update")
        # 1) Download latest SecurityMaster
        download_and_extract_security_master(destination_dir=self.root_dir)
        # 2) Upsert into DB
        written = populate_instruments_from_security_master(self.root_dir)
        logger.info("Daily instruments update complete: {} rows upserted", written)


