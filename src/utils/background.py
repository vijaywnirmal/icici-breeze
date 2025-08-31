from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, Optional

from .response import log_exception


class BackgroundRunner:
	"""Lightweight task runner for periodic/one-off async tasks.

	All tasks are best-effort; exceptions are logged and swallowed.
	"""

	def __init__(self) -> None:
		self._tasks: List[asyncio.Task] = []
		self._running = False

	async def start(self) -> None:
		self._running = True

	async def stop(self) -> None:
		self._running = False
		for t in self._tasks:
			try:
				t.cancel()
			except Exception:
				pass
		await asyncio.gather(*self._tasks, return_exceptions=True)
		self._tasks.clear()

	def schedule_once(self, coro: Awaitable[object]) -> None:
		if not self._running:
			return
		self._tasks.append(asyncio.create_task(self._wrap(coro)))

	def schedule_periodic(self, fn: Callable[[], Awaitable[object]], interval_seconds: int) -> None:
		if not self._running:
			return
		self._tasks.append(asyncio.create_task(self._periodic(fn, interval_seconds)))

	async def _wrap(self, coro: Awaitable[object]) -> None:
		try:
			await coro
		except asyncio.CancelledError:
			return
		except Exception as exc:
			log_exception(exc, context="background.wrap")

	async def _periodic(self, fn: Callable[[], Awaitable[object]], interval_seconds: int) -> None:
		while self._running:
			try:
				await fn()
			except asyncio.CancelledError:
				return
			except Exception as exc:
				log_exception(exc, context="background.periodic")
			try:
				await asyncio.sleep(interval_seconds)
			except asyncio.CancelledError:
				return


