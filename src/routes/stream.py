from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
import contextlib
from typing import Any, Dict, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..utils.response import log_exception
from ..services.breeze_service import BreezeService
from ..utils.session import get_breeze
from ..services.quotes_cache import get_cached_quote, upsert_quote
from .quotes import _is_market_open_ist, _last_session_close_range_utc, _to_breeze_iso

router = APIRouter(tags=["stream"])


@dataclass
class ConnectionState:
    """Per-connection registry for subscriptions and flow control."""
    symbol: Optional[str] = None
    last_sent_ts: float = 0.0
    min_interval_ms: int = 250
    breeze: Optional[BreezeService] = None


@router.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket) -> None:
    await websocket.accept()
    state = ConnectionState()
    breeze_ws_connected = False
    loop = asyncio.get_running_loop()

    async def forward_tick(tick: Dict[str, Any]) -> None:
        now = time.monotonic() * 1000.0
        if now - state.last_sent_ts < state.min_interval_ms:
            return
        state.last_sent_ts = now

        normalized = {
            "type": "tick",
            "symbol": state.symbol,
            "ltp": tick.get("last") or tick.get("ltp") or tick.get("close") or tick.get("open"),
            "close": tick.get("close"),
            "bid": tick.get("bPrice") or tick.get("best_bid_price"),
            "ask": tick.get("sPrice") or tick.get("best_ask_price"),
            "change_pct": tick.get("change") or tick.get("pChange"),
            "timestamp": tick.get("ltt") or tick.get("datetime") or tick.get("timestamp"),
        }
        await websocket.send_text(json.dumps(normalized))

    async def send_last_close(symbol: str) -> None:
        """Send last close price using cached quote or historical data."""
        cached = get_cached_quote(symbol)
        if cached:
            await websocket.send_text(json.dumps({
                "type": "tick",
                **cached,
                "note": "market closed; using cache"
            }))
            return

        try:
            if not state.breeze:
                runtime = get_breeze()
                if runtime is not None:
                    state.breeze = runtime
                else:
                    raise RuntimeError("No Breeze session. Login required.")

            f_utc, t_utc = _last_session_close_range_utc()
            resp = state.breeze.client.get_historical_data_v2(
                interval="1minute",
                from_date=_to_breeze_iso(f_utc),
                to_date=_to_breeze_iso(t_utc),
                stock_code=symbol,
                exchange_code="NSE",
                product_type="cash"
            )
            success = resp.get("Success") or []
            if success:
                last_bar = success[-1]
                timestamp = datetime.strptime(last_bar["datetime"], "%Y-%m-%d %H:%M:%S") \
                                    .replace(tzinfo=ZoneInfo("Asia/Kolkata")) \
                                    .astimezone(ZoneInfo("UTC")) \
                                    .isoformat().replace("+00:00", "Z")
                payload = {
                    "type": "tick",
                    "symbol": symbol,
                    "ltp": last_bar.get("close"),
                    "close": last_bar.get("close"),
                    "bid": None,
                    "ask": None,
                    "change_pct": None,
                    "timestamp": timestamp,
                    "note": "market closed; historical last close"
                }
                await websocket.send_text(json.dumps(payload))
                try:
                    upsert_quote(symbol, payload)
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.send_last_close.cache_upsert")
        except Exception as exc:
            log_exception(exc, context="ws_ticks.send_last_close")

    try:
        while True:
            msg_text = await websocket.receive_text()
            try:
                msg = json.loads(msg_text)
            except Exception:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "context": "parse",
                    "message": "Invalid JSON"
                }))
                continue

            action = (msg.get("action") or "").lower()

            if action == "subscribe":
                symbol = (msg.get("symbol") or "").upper()
                if not symbol:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "context": "subscribe",
                        "message": "symbol required"
                    }))
                    continue
                state.symbol = symbol

                if not _is_market_open_ist():
                    await send_last_close(symbol)
                    await websocket.send_text(json.dumps({
                        "type": "info",
                        "message": "Market closed; WS subscription skipped"
                    }))
                    continue

                await websocket.send_text(json.dumps({
                    "type": "info",
                    "message": "Connecting to Breeze WS..."
                }))
                try:
                    if not state.breeze:
                        runtime = get_breeze()
                        if runtime is not None:
                            state.breeze = runtime
                        else:
                            raise RuntimeError("No Breeze session. Login required.")
                    state.breeze.client.ws_connect()
                    breeze_ws_connected = True
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.ws_connect")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "context": "ws_connect",
                        "message": str(exc)
                    }))
                    await websocket.close()
                    return

                try:
                    state.breeze.client.subscribe_feeds(
                        exchange_code="NSE",
                        stock_code=symbol,
                        product_type="cash",
                        get_market_depth=False,
                        get_exchange_quotes=True,
                    )

                    def on_ticks(ticks: Dict[str, Any]) -> None:
                        asyncio.run_coroutine_threadsafe(forward_tick(ticks), loop)

                    state.breeze.client.on_ticks = on_ticks
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.subscribe")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "context": "subscribe",
                        "message": str(exc)
                    }))

                await websocket.send_text(json.dumps({
                    "type": "subscribed",
                    "symbol": symbol
                }))

            elif action == "unsubscribe":
                try:
                    if state.symbol and state.breeze:
                        state.breeze.client.unsubscribe_feeds(
                            exchange_code="NSE",
                            stock_code=state.symbol,
                            product_type="cash"
                        )
                        state.breeze.client.on_ticks = None
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed",
                            "symbol": state.symbol
                        }))
                        state.symbol = None
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.unsubscribe")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "context": "unsubscribe",
                        "message": str(exc)
                    }))
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "context": "action",
                    "message": "Unknown action"
                }))

    except WebSocketDisconnect:
        try:
            if state.breeze and state.symbol:
                state.breeze.client.unsubscribe_feeds(
                    exchange_code="NSE",
                    stock_code=state.symbol,
                    product_type="cash"
                )
                state.breeze.client.on_ticks = None
            if state.breeze and breeze_ws_connected:
                state.breeze.client.ws_disconnect()
        except Exception as exc:
            log_exception(exc, context="ws_ticks.disconnect_cleanup")
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
