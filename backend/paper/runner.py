"""Background loop: keep the paper record current whenever a Breeze session is available.

Runs inside the backend (started from app startup). Each tick is cheap when there is nothing new: the
engine only processes sessions after the ledger's last_processed date.
"""
from __future__ import annotations

import asyncio
import logging

from ..utils.session import get_breeze
from . import ledger as L
from .config import load_config
from .market import BreezeMarket

INTERVAL_SECONDS = 15 * 60
log = logging.getLogger("paper")


class PaperRunner:
    def __init__(self, interval: int = INTERVAL_SECONDS):
        self.interval = interval
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            try:
                breeze = await asyncio.to_thread(get_breeze)  # may touch Redis / the network: keep it off the event loop
                if breeze is not None:
                    ledger = await asyncio.to_thread(L.run_step, BreezeMarket(breeze.client, load_config().symbol))
                    log.info("paper record current to %s", ledger["last_processed"])
            except Exception as exc:  # a bad tick must not kill the loop
                log.warning("paper step failed: %s", exc)
            await asyncio.sleep(self.interval)
