from __future__ import annotations

import asyncio
import time
import contextlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..utils.response import log_exception
from .breeze_service import BreezeService


@dataclass
class ItemState:
	"""Tracks per-symbol state and latest quote fields for coalescing."""
	symbol: str
	last_sent_ms: float = 0.0
	last_quote: Dict[str, Any] = field(default_factory=dict)


class WatchlistWSService:
	"""Manages streaming updates for a user's watchlist via Breeze WS and REST polling.

	- Attempts to connect Breeze websocket and subscribe to symbols
	- Falls back to periodic REST polling when closed or WS unavailable
	- Coalesces outgoing updates to at most every `min_send_interval_ms`
	"""

	def __init__(self, symbols: List[str], min_send_interval_ms: int = 300, poll_interval_s: int = 45) -> None:
		self._symbols = [s.upper() for s in symbols]
		self._min_send_interval_ms = max(100, min_send_interval_ms)
		self._poll_interval_s = max(15, poll_interval_s)
		self._breeze: Optional[BreezeService] = None
		self._states: Dict[str, ItemState] = {s: ItemState(symbol=s) for s in self._symbols}
		self._send_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
		self._tasks: List[asyncio.Task] = []
		self._closed: bool = False

	def _now_ms(self) -> float:
		return time.monotonic() * 1000.0

	def attach_breeze(self, breeze: Optional[BreezeService]) -> None:
		self._breeze = breeze

	def _coalesce_and_enqueue(self, symbol: str, tick: Dict[str, Any]) -> None:
		state = self._states.get(symbol)
		if not state:
			state = ItemState(symbol)
			self._states[symbol] = state

		# Normalize fields
		ltp = tick.get("last") or tick.get("ltp") or tick.get("close") or tick.get("open")
		bid = tick.get("bPrice") or tick.get("best_bid_price")
		ask = tick.get("sPrice") or tick.get("best_ask_price")
		change_pct = tick.get("change") or tick.get("pChange")
		ts = tick.get("ltt") or tick.get("datetime") or tick.get("timestamp")

		state.last_quote = {
			"symbol": symbol,
			"ltp": ltp,
			"change_pct": change_pct,
			"bid": bid,
			"ask": ask,
			"ts": ts,
		}

		# Debounce per symbol
		now = self._now_ms()
		if now - state.last_sent_ms >= self._min_send_interval_ms:
			state.last_sent_ms = now
			self._send_queue.put_nowait(state.last_quote)

	async def _sender(self, send_text: callable) -> None:
		"""Drains the coalesced queue and sends updates to the client."""
		try:
			while not self._closed:
				try:
					msg = await asyncio.wait_for(self._send_queue.get(), timeout=0.5)
					await send_text(msg)
				except asyncio.TimeoutError:
					continue
		except Exception as exc:
			log_exception(exc, context="WatchlistWSService._sender")

	async def _poller(self) -> None:
		"""Poll REST quotes periodically as a fallback when WS is idle or markets are closed.

		This uses Breeze REST methods if a client is present; errors are swallowed.
		"""
		try:
			while not self._closed:
				await asyncio.sleep(self._poll_interval_s)
				for symbol in list(self._states.keys()):
					if self._closed:
						return
					try:
						if self._breeze:
							# Best-effort: attempt to retrieve quotes; signature may vary
							quote = self._breeze.client.get_quotes(stock_code=symbol)  # type: ignore[attr-defined]
							if isinstance(quote, dict):
								self._coalesce_and_enqueue(symbol, quote)
					except Exception as exc:
						log_exception(exc, context="WatchlistWSService._poller", symbol=symbol)
		except Exception as exc:
			log_exception(exc, context="WatchlistWSService._poller.run")

	def _subscribe_ws(self) -> None:
		"""Subscribe all symbols on Breeze websocket if available."""
		if not self._breeze:
			return
		try:
			self._breeze.client.ws_connect()
			def on_ticks(ticks: Dict[str, Any]) -> None:
				try:
					symbol = (ticks.get("symbol") or ticks.get("stock_code") or "").upper()
					if symbol:
						self._coalesce_and_enqueue(symbol, ticks)
				except Exception as exc:
					log_exception(exc, context="WatchlistWSService.on_ticks")
			self._breeze.client.on_ticks = on_ticks
			for s in self._symbols:
				# Best-effort subscription; real impl should map symbol -> stock_token
				try:
					self._breeze.client.subscribe_feeds(stock_token=s)
				except Exception as exc:
					log_exception(exc, context="WatchlistWSService.subscribe_feeds", symbol=s)
		except Exception as exc:
			log_exception(exc, context="WatchlistWSService._subscribe_ws")

	async def start(self, send_text: callable) -> None:
		"""Start sender and poller tasks. Call once per connection."""
		self._tasks.append(asyncio.create_task(self._sender(send_text)))
		self._tasks.append(asyncio.create_task(self._poller()))
		# Attempt WS subscription (non-blocking)
		await asyncio.get_event_loop().run_in_executor(None, self._subscribe_ws)

	async def stop(self) -> None:
		self._closed = True
		for t in self._tasks:
			try:
				t.cancel()
			except Exception:
				pass
		try:
			if self._breeze:
				for s in self._symbols:
					with contextlib.suppress(Exception):
						self._breeze.client.unsubscribe_feeds(stock_token=s)
				with contextlib.suppress(Exception):
					self._breeze.client.ws_disconnect()
		except Exception as exc:
			log_exception(exc, context="WatchlistWSService.stop")
