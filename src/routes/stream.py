from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
import contextlib
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..utils.response import log_exception
from ..services.breeze_service import BreezeService


router = APIRouter(tags=["stream"])  # websocket path will be absolute


@dataclass
class ConnectionState:
	"""Per-connection registry for subscriptions and flow control."""
	symbol: Optional[str] = None
	last_sent_ts: float = 0.0
	min_interval_ms: int = 250  # debounce tick forwarding per connection
	breeze: Optional[BreezeService] = None


@router.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket) -> None:
	await websocket.accept()

	state = ConnectionState()

	# Initialize Breeze service on demand after receiving subscribe
	breeze_ws_connected = False

	async def forward_tick(tick: Dict[str, Any]) -> None:
		# Debounce: only forward if enough time has elapsed
		now = time.monotonic() * 1000.0
		if now - state.last_sent_ts < state.min_interval_ms:
			return
		state.last_sent_ts = now

		# Normalize tick fields (best-effort; Breeze provides several quote shapes)
		normalized = {
			"symbol": state.symbol,
			"ltp": tick.get("last") or tick.get("ltp") or tick.get("close") or tick.get("open"),
			"bid": tick.get("bPrice") or tick.get("best_bid_price"),
			"ask": tick.get("sPrice") or tick.get("best_ask_price"),
			"change_pct": tick.get("change") or tick.get("pChange"),
			"timestamp": tick.get("ltt") or tick.get("datetime") or tick.get("timestamp"),
		}
		await websocket.send_text(json.dumps(normalized))

	try:
		while True:
			msg_text = await websocket.receive_text()
			try:
				msg = json.loads(msg_text)
			except Exception:
				await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
				continue

			action = (msg.get("action") or "").lower()
			if action == "subscribe":
				# Expect symbol/exchange_code/product_type
				symbol = (msg.get("symbol") or "").upper()
				if not symbol:
					await websocket.send_text(json.dumps({"type": "error", "message": "symbol required"}))
					continue
				state.symbol = symbol

				# Create Breeze and connect ws if not already
				if not state.breeze:
					# NOTE: In a real app you'd source keys from secure session; here we expect env or runtime provisioning
					await websocket.send_text(json.dumps({"type": "info", "message": "Connecting to Breeze WS..."}))
					try:
						# Placeholder: breeze requires valid credentials which should already be generated post-login
						# Here we initialize the service without regenerating session; the session must be valid in process
						# For MVP, we just construct the service with a dummy key; real integration should reuse user's session
						service = BreezeService(api_key="")
						state.breeze = service
						service.client.ws_connect()
						breeze_ws_connected = True
					except Exception as exc:
						log_exception(exc, context="ws_ticks.ws_connect")
						await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
						await websocket.close()
						return

				# Subscribe to quotes/feeds for the symbol
				try:
					# For indices with quotes stream, subscribe_feeds with stock_token/symbol may vary by API.
					# Breeze docs show subscribe_feeds(stock_token="4.1!2885") or subscribe_feeds(..., interval="1minute")
					# For MVP, attempt symbol-based feed subscribe if supported; else this is where mapping would occur.
					state.breeze.client.subscribe_feeds(stock_token=symbol)

					# Assign callback to forward ticks
					def on_ticks(ticks: Dict[str, Any]) -> None:
						# Schedule send in event loop with debounce
						asyncio.run_coroutine_threadsafe(forward_tick(ticks), asyncio.get_event_loop())

					state.breeze.client.on_ticks = on_ticks
				except Exception as exc:
					log_exception(exc, context="ws_ticks.subscribe")
					await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))

				await websocket.send_text(json.dumps({"type": "subscribed", "symbol": symbol}))

			elif action == "unsubscribe":
				try:
					# No-op if symbol unknown; in full impl, map symbol -> stock_token and unsubscribe accordingly
					if state.symbol:
						# Attempt generic unsubscribe
						state.breeze and state.breeze.client.unsubscribe_feeds(stock_token=state.symbol)
						await websocket.send_text(json.dumps({"type": "unsubscribed", "symbol": state.symbol}))
						state.symbol = None
				except Exception as exc:
					log_exception(exc, context="ws_ticks.unsubscribe")
					await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
			else:
				await websocket.send_text(json.dumps({"type": "error", "message": "Unknown action"}))

	except WebSocketDisconnect:
		# Cleanup on disconnect
		try:
			if state.breeze and state.symbol:
				state.breeze.client.unsubscribe_feeds(stock_token=state.symbol)
			if state.breeze and breeze_ws_connected:
				state.breeze.client.ws_disconnect()
		except Exception as exc:
			log_exception(exc, context="ws_ticks.disconnect_cleanup")
	finally:
		# Ensure closed
		with contextlib.suppress(Exception):
			await websocket.close()
