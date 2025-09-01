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
from ..utils.config import settings
from ..services.quotes_cache import get_cached_quote, upsert_quote
from ..services.ws_stream_manager import STREAM_MANAGER
from .quotes import _is_market_open_ist, _last_session_close_range_utc, _to_breeze_iso

router = APIRouter(tags=["stream"])


@dataclass
class ConnectionState:
    """Per-connection registry for subscriptions and flow control."""
    symbol: Optional[str] = None
    exchange_code: str = "NSE"
    product_type: str = "cash"
    last_sent_ts: float = 0.0
    last_sent_ts_by_symbol: Dict[str, float] | None = None
    subscriptions: Dict[str, Dict[str, str]] | None = None
    min_interval_ms: int = 250
    breeze: Optional[BreezeService] = None


@router.websocket("/ws/ticks")
async def ws_ticks(websocket: WebSocket) -> None:
    await websocket.accept()
    state = ConnectionState()
    state.last_sent_ts_by_symbol = {}
    state.subscriptions = {}
    breeze_ws_connected = False
    loop = asyncio.get_running_loop()
    STREAM_MANAGER.set_loop(loop)
    STREAM_MANAGER.register_client(websocket, loop)

    def _extract_symbol_from_tick(tick: Dict[str, Any]) -> Optional[str]:
        raw = tick.get("stock_code") or tick.get("symbol") or tick.get("stock_code_name") or tick.get("security_id") or tick.get("scrip_id")
        if not raw:
            return state.symbol
        try:
            code = str(raw).upper().strip()
            if code.endswith(".NS"):
                code = code[:-3]
            return code
        except Exception:
            return state.symbol

    async def forward_tick(tick: Dict[str, Any]) -> None:
        now = time.monotonic() * 1000.0
        sym = _extract_symbol_from_tick(tick) or state.symbol or ""
        last = state.last_sent_ts_by_symbol.get(sym, 0.0) if state.last_sent_ts_by_symbol is not None else 0.0
        if now - last < state.min_interval_ms:
            return
        if state.last_sent_ts_by_symbol is not None:
            state.last_sent_ts_by_symbol[sym] = now

        normalized = {
            "type": "tick",
            "symbol": sym,
            "ltp": tick.get("last") or tick.get("ltp") or tick.get("close") or tick.get("open"),
            "close": tick.get("close"),
            "bid": tick.get("bPrice") or tick.get("best_bid_price"),
            "ask": tick.get("sPrice") or tick.get("best_ask_price"),
            "change_pct": tick.get("change") or tick.get("pChange"),
            "timestamp": tick.get("ltt") or tick.get("datetime") or tick.get("timestamp"),
        }
        await websocket.send_text(json.dumps(normalized))

    def _ensure_breeze_runtime() -> Optional[BreezeService]:
        """Ensure a BreezeService is available from runtime or .env fallback."""
        try:
            runtime = get_breeze()
            if runtime is not None:
                return runtime
            # Fallback to environment-based login if all creds present
            if settings.breeze_api_key and settings.breeze_api_secret and settings.breeze_session_token:
                svc = BreezeService(api_key=settings.breeze_api_key)
                result = svc.login_and_fetch_profile(
                    api_secret=settings.breeze_api_secret,
                    session_key=settings.breeze_session_token,
                )
                if result.success:
                    return svc
        except Exception as exc:
            log_exception(exc, context="ws_ticks.ensure_breeze_runtime")
        return None

    async def send_last_close(symbol: str, exchange_code: str) -> None:
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
                state.breeze = _ensure_breeze_runtime()
            if not state.breeze:
                # No session available; skip historical fetch and return
                await websocket.send_text(json.dumps({
                    "type": "info",
                    "message": "No Breeze session. Using cache only.",
                }))
                return

            f_utc, t_utc = _last_session_close_range_utc()
            resp = state.breeze.client.get_historical_data_v2(
                interval="1minute",
                from_date=_to_breeze_iso(f_utc),
                to_date=_to_breeze_iso(t_utc),
                stock_code=symbol,
                exchange_code=exchange_code or "NSE",
                product_type=state.product_type or "cash"
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
                # Allow client to specify exchange/product; default to NSE/cash
                state.exchange_code = (msg.get("exchange_code") or "NSE").upper()
                state.product_type = (msg.get("product_type") or "cash").lower()

                if not _is_market_open_ist():
                    await send_last_close(symbol, state.exchange_code)
                    await websocket.send_text(json.dumps({
                        "type": "info",
                        "message": "Market closed; WS subscription skipped"
                    }))
                    continue

                await websocket.send_text(json.dumps({
                    "type": "info",
                    "message": "Subscribing via stream manager..."
                }))
                try:
                    STREAM_MANAGER.subscribe(symbol, state.exchange_code, state.product_type)
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.manager_subscribe_single")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "context": "manager_subscribe",
                        "message": str(exc)
                    }))

                await websocket.send_text(json.dumps({
                    "type": "subscribed",
                    "symbol": symbol
                }))
                # Ensure central stream subscription
                try:
                    STREAM_MANAGER.subscribe(symbol, state.exchange_code, state.product_type)
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.manager_subscribe")

            elif action == "subscribe_many":
                items = msg.get("symbols") or []
                if not isinstance(items, list) or not items:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "context": "subscribe_many",
                        "message": "symbols list required"
                    }))
                    continue

                if not _is_market_open_ist():
                    for it in items:
                        try:
                            code = str((it.get("stock_code") or it.get("symbol") or "")).upper()
                            if not code:
                                continue
                            ex = str((it.get("exchange_code") or "NSE")).upper()
                            await send_last_close(code, ex)
                        except Exception as exc:
                            log_exception(exc, context="ws_ticks.subscribe_many.closed")
                    await websocket.send_text(json.dumps({
                        "type": "info",
                        "message": "Market closed; WS subscription skipped"
                    }))
                    continue

                try:
                    STREAM_MANAGER.subscribe_many(items)
                    for it in items:
                        try:
                            code = str((it.get("stock_code") or it.get("symbol") or "")).upper()
                            if code:
                                await websocket.send_text(json.dumps({"type": "subscribed", "symbol": code}))
                        except Exception:
                            pass
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.subscribe_many_manager")
                    await websocket.send_text(json.dumps({"type": "error", "context": "subscribe_many_manager", "message": str(exc)}))

            elif action == "unsubscribe":
                try:
                    if state.symbol and state.breeze:
                        state.breeze.client.unsubscribe_feeds(
                            exchange_code=state.exchange_code,
                            stock_code=state.symbol,
                            product_type=state.product_type
                        )
                        state.breeze.client.on_ticks = None
                        await websocket.send_text(json.dumps({
                            "type": "unsubscribed",
                            "symbol": state.symbol
                        }))
                        try:
                            STREAM_MANAGER.unsubscribe(state.symbol)
                        except Exception as exc:
                            log_exception(exc, context="ws_ticks.manager_unsubscribe")
                        state.symbol = None
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.unsubscribe")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "context": "unsubscribe",
                        "message": str(exc)
                    }))
            elif action == "unsubscribe_many":
                items = msg.get("symbols") or []
                if not isinstance(items, list) or not items:
                    await websocket.send_text(json.dumps({"type": "error", "context": "unsubscribe_many", "message": "symbols list required"}))
                    continue
                try:
                    STREAM_MANAGER.unsubscribe_many(items)
                    for it in items:
                        try:
                            code = str((it.get("stock_code") or it.get("symbol") or "")).upper()
                            if code:
                                await websocket.send_text(json.dumps({"type": "unsubscribed", "symbol": code}))
                        except Exception:
                            pass
                except Exception as exc:
                    log_exception(exc, context="ws_ticks.unsubscribe_many")
                    await websocket.send_text(json.dumps({"type": "error", "context": "unsubscribe_many", "message": str(exc)}))
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "context": "action",
                    "message": "Unknown action"
                }))

    except WebSocketDisconnect:
        try:
            pass
        except Exception as exc:
            log_exception(exc, context="ws_ticks.disconnect_cleanup")
    finally:
        with contextlib.suppress(Exception):
            STREAM_MANAGER.unregister_client(websocket)
            await websocket.close()
