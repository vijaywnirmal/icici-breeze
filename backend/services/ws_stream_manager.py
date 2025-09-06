from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Set
import re

from ..utils.response import log_exception
from ..utils.config import settings
from ..utils.session import get_breeze
from .breeze_service import BreezeService


class BreezeSocketService:
    """Singleton manager for a single Breeze WS connection and fan-out to clients."""

    def __init__(self) -> None:
        self._breeze: Optional[BreezeService] = None
        self._connected = False
        self._clients: Set[Any] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._subscriptions: Dict[str, Dict[str, str]] = {}

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _ensure_breeze(self) -> Optional[BreezeService]:
        if self._breeze is not None:
            return self._breeze
        try:
            runtime = get_breeze()
            if runtime is not None:
                self._breeze = runtime
                return self._breeze
            # No fallback - user must login first
            log_exception(Exception("No active Breeze session found"), context="BreezeSocketService.ensure_breeze")
        except Exception as exc:
            log_exception(exc, context="BreezeSocketService.ensure_breeze")
        return None

    def connect(self) -> None:
        if self._connected:
            return
        svc = self._ensure_breeze()
        if not svc:
            raise RuntimeError("No Breeze session available")
        try:
            # Register tick handler BEFORE establishing the WS connection
            def on_ticks(ticks: Dict[str, Any]) -> None:
                try:
                    # Normalize minimal payload
                    raw_sym = ticks.get("stock_code") or ticks.get("symbol") or ""
                    raw_sym_u = str(raw_sym).upper()
                    raw_token = ticks.get("stock_token") or ticks.get("token") or ""
                    raw_token_u = str(raw_token).upper()
                    # Prefer alias mapping by token, then by stock_code/symbol
                    alias = None
                    if raw_token_u:
                        sub = self._subscriptions.get(raw_token_u)
                        if isinstance(sub, dict):
                            alias = sub.get("alias") or alias
                    if not alias and raw_sym_u:
                        sub2 = self._subscriptions.get(raw_sym_u)
                        if isinstance(sub2, dict):
                            alias = sub2.get("alias") or alias
                    # Build option-chain alias if fields present
                    expiry_raw = ticks.get("expiry_date") or ticks.get("expiry")
                    strike_raw = ticks.get("strike_price") or ticks.get("strike")
                    right_raw = ticks.get("right_type") or ticks.get("right") or ticks.get("option_type")
                    alias_from_tick = None
                    try:
                        if expiry_raw and strike_raw and right_raw:
                            right_u = str(right_raw).upper()
                            right_txt = "CALL" if right_u in ("CE", "CALL") else ("PUT" if right_u in ("PE", "PUT") else right_u)
                            alias_from_tick = f"{raw_sym_u}|{expiry_raw}|{right_txt}|{strike_raw}"
                    except Exception:
                        alias_from_tick = None

                    symbol = alias_from_tick or alias or raw_sym_u or raw_token_u
                    if symbol.endswith(".NS"):
                        symbol = symbol[:-3]
                    payload = {
                        "type": "tick",
                        "symbol": symbol,
                        "token": raw_token_u or None,
                        "exchange_code": ticks.get("exchange_code"),
                        "interval": ticks.get("interval"),
                        "expiry_date": ticks.get("expiry_date") or ticks.get("expiry"),
                        "strike_price": ticks.get("strike_price") or ticks.get("strike"),
                        "right_type": ticks.get("right_type") or ticks.get("right") or ticks.get("option_type"),
                        "ltp": ticks.get("last") or ticks.get("ltp") or ticks.get("close") or ticks.get("open"),
                        "close": ticks.get("close"),
                        "bid": ticks.get("bPrice") or ticks.get("best_bid_price"),
                        "ask": ticks.get("sPrice") or ticks.get("best_ask_price"),
                        "change_pct": ticks.get("change") or ticks.get("pChange"),
                        "timestamp": ticks.get("ltt") or ticks.get("datetime") or ticks.get("timestamp"),
                    }
                    if self._loop is not None:
                        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)
                except Exception as exc:
                    log_exception(exc, context="BreezeSocketService.on_ticks")

            svc.client.on_ticks = on_ticks
            # Now open the websocket connection
            svc.client.ws_connect()
            self._connected = True
        except Exception as exc:
            log_exception(exc, context="BreezeSocketService.connect")
            raise

    def subscribe(self, stock_code: str, exchange_code: str = "NSE", product_type: str = "cash") -> None:
        svc = self._ensure_breeze()
        if not svc:
            raise RuntimeError("No Breeze session available")
        if not self._connected:
            self.connect()
        code = (stock_code or "").upper()
        if not code:
            return
        # If client sent a bare numeric token (e.g., '2885'), convert to full token and subscribe as token
        if re.fullmatch(r"\d+", code):
            try:
                prefix = "4.1!" if exchange_code.upper() == "NSE" else "1.1!"
                token_code = f"{prefix}{code}"
                self._subscriptions[token_code.upper()] = {"exchange_code": "TOKEN", "product_type": product_type.lower(), "alias": code}
                svc.client.subscribe_feeds(stock_token=[token_code])
                return
            except Exception as exc:
                log_exception(exc, context="BreezeSocketService.subscribe.numeric_token", symbol=code)
                # fallthrough to normal path if token subscribe failed
        self._subscriptions[code] = {"exchange_code": exchange_code.upper(), "product_type": product_type.lower(), "alias": code}
        try:
            # Support token-based subscription when code looks like X.Y!TOKEN
            token_pattern = re.compile(r"^\d+\.\d+!.+$")
            if token_pattern.match(code):
                svc.client.subscribe_feeds(stock_token=[code])
            else:
                svc.client.subscribe_feeds(
                    exchange_code=exchange_code.upper(),
                    stock_code=code,
                    product_type=product_type.lower(),
                    get_market_depth=False,
                    get_exchange_quotes=True,
                )
        except Exception as exc:
            log_exception(exc, context="BreezeSocketService.subscribe", symbol=code)

    def subscribe_many(self, items: list[dict[str, str]]) -> None:
        # Collect tokens, regular stock_codes, and options separately for efficient subscribe
        token_list: list[str] = []
        regular: list[tuple[str, str, str]] = []
        options_items: list[dict[str, str]] = []
        for it in items:
            code = str(it.get("stock_code") or it.get("symbol") or "")
            provided_alias = str(it.get("alias") or "").strip()
            raw_token = it.get("token")
            # Only process token if it's a valid string and not empty/undefined
            if raw_token and str(raw_token) not in ("", "undefined", "null"):
                raw_token_str = str(raw_token)
                # Normalize token to X.Y!TOKEN. Default NSE (4.1!) when exchange_code missing
                ex = str(it.get("exchange_code") or "NSE").upper()
                token = raw_token_str
                if not re.match(r"^\d+\.\d+!.+$", token):
                    prefix = "4.1!" if ex == "NSE" else "1.1!"
                    token = f"{prefix}{raw_token_str}"
                token_list.append(token)
                # Preserve alias mapping for token → display code
                alias = provided_alias or (str(code).upper() if code else token.upper())
                self._subscriptions[token.upper()] = {"exchange_code": "TOKEN", "product_type": "cash", "alias": alias}
            elif code:
                prod = str(it.get("product_type") or "cash").lower()
                if prod == "options" and (it.get("expiry_date") or it.get("expiry")) and it.get("strike_price") and (it.get("right") or it.get("right_type")):
                    options_items.append(it)
                else:
                    ex = str(it.get("exchange_code") or "NSE").upper()
                    regular.append((code, ex, str(it.get("product_type") or "cash")))

        if token_list:
            svc = self._ensure_breeze()
            if not svc:
                raise RuntimeError("No Breeze session available")
            if not self._connected:
                self.connect()
            try:
                svc.client.subscribe_feeds(stock_token=token_list)
                # Preserve existing alias mapping if already set for token
                for t in token_list:
                    existing = self._subscriptions.get(t)
                    alias = existing.get("alias") if isinstance(existing, dict) else None
                    self._subscriptions[t] = {"exchange_code": "TOKEN", "product_type": "cash", **({"alias": alias} if alias else {})}
            except Exception as exc:
                log_exception(exc, context="BreezeSocketService.subscribe_many.tokens")

        for code, ex, prod in regular:
            try:
                self.subscribe(code, ex, prod)
            except Exception:
                continue

        # Subscribe options individually (Breeze does not batch param-style options)
        if options_items:
            svc = self._ensure_breeze()
            if not svc:
                raise RuntimeError("No Breeze session available")
            if not self._connected:
                self.connect()
            for it in options_items:
                try:
                    ex = str(it.get("exchange_code") or "NFO").upper()
                    prod = "options"
                    code = str(it.get("stock_code") or it.get("symbol") or "").upper()
                    expiry = it.get("expiry_date") or it.get("expiry")
                    strike = str(it.get("strike_price"))
                    right = str(it.get("right") or it.get("right_type") or "").lower()
                    interval = it.get("interval") or "1minute"
                    svc.client.subscribe_feeds(
                        exchange_code=ex,
                        stock_code=code,
                        expiry_date=expiry,
                        strike_price=strike,
                        right=right,
                        product_type=prod,
                        get_market_depth=False,
                        get_exchange_quotes=True,
                        interval=interval,
                    )
                    # Save alias mapping for clarity
                    right_u = right.upper()
                    right_txt = "CALL" if right_u in ("CE", "CALL") else ("PUT" if right_u in ("PE", "PUT") else right_u)
                    alias = str(it.get("alias") or f"{code}|{expiry}|{right_txt}|{strike}")
                    self._subscriptions[alias.upper()] = {"exchange_code": ex, "product_type": prod, "alias": alias}
                except Exception as exc:
                    log_exception(exc, context="BreezeSocketService.subscribe_many.options")

    def unsubscribe(self, stock_code: str) -> None:
        svc = self._breeze
        if not svc:
            return
        code = (stock_code or "").upper()
        sub = self._subscriptions.get(code)
        if not sub:
            return
        try:
            if sub.get("exchange_code") == "TOKEN" or (code and ('!' in code)):
                svc.client.unsubscribe_feeds(stock_token=[code])
            else:
                svc.client.unsubscribe_feeds(
                    exchange_code=sub.get("exchange_code", "NSE"),
                    stock_code=code,
                    product_type=sub.get("product_type", "cash"),
                )
        except Exception as exc:
            log_exception(exc, context="BreezeSocketService.unsubscribe", symbol=code)
        finally:
            self._subscriptions.pop(code, None)

    def unsubscribe_many(self, items: list[dict[str, str]]) -> None:
        for it in items:
            try:
                code = str(it.get("stock_code") or it.get("symbol") or "")
                if code:
                    self.unsubscribe(code)
            except Exception:
                continue

    def register_client(self, ws: Any, loop: asyncio.AbstractEventLoop | None = None) -> None:
        if loop is not None:
            self._loop = loop
        self._clients.add(ws)

    def unregister_client(self, ws: Any) -> None:
        try:
            self._clients.discard(ws)
        except Exception:
            pass

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload)
        coros = []
        for ws in list(self._clients):
            try:
                coros.append(ws.send_text(data))
            except Exception:
                # Drop dead clients lazily
                self._clients.discard(ws)
        if coros:
            try:
                await asyncio.gather(*coros, return_exceptions=True)
            except Exception:
                pass


STREAM_MANAGER = BreezeSocketService()


