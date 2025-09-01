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
            if settings.breeze_api_key and settings.breeze_api_secret and settings.breeze_session_token:
                svc = BreezeService(api_key=settings.breeze_api_key)
                res = svc.login_and_fetch_profile(
                    api_secret=settings.breeze_api_secret,
                    session_key=settings.breeze_session_token,
                )
                if res.success:
                    self._breeze = svc
                    return self._breeze
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
            svc.client.ws_connect()

            def on_ticks(ticks: Dict[str, Any]) -> None:
                try:
                    # Normalize minimal payload
                    raw_sym = ticks.get("stock_code") or ticks.get("symbol") or ""
                    raw_sym_u = str(raw_sym).upper()
                    # Map to subscription alias if present (ensures 'NIFTY', 'BSESEN', etc.)
                    alias = self._subscriptions.get(raw_sym_u, {}).get("alias") if isinstance(self._subscriptions.get(raw_sym_u), dict) else None
                    symbol = alias or raw_sym_u
                    if symbol.endswith(".NS"):
                        symbol = symbol[:-3]
                    payload = {
                        "type": "tick",
                        "symbol": symbol,
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
        self._subscriptions[code] = {"exchange_code": exchange_code.upper(), "product_type": product_type.lower(), "alias": code}
        try:
            # Support token-based subscription when code looks like X.Y!TOKEN
            token_pattern = re.compile(r"^\d+\.\d+!\w+$")
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
        # Collect tokens and regular stock_codes separately for efficient batch subscribe
        token_list: list[str] = []
        regular: list[tuple[str, str, str]] = []
        for it in items:
            code = str(it.get("stock_code") or it.get("symbol") or "")
            raw_token = str(it.get("token") or "")
            # Normalize token to X.Y!TOKEN. Default NSE (4.1!) when exchange_code missing
            ex = str(it.get("exchange_code") or "NSE").upper()
            if raw_token:
                token = raw_token
                if not re.match(r"^\d+\.\d+!\w+$", token):
                    prefix = "4.1!" if ex == "NSE" else "1.1!"
                    token = f"{prefix}{raw_token}"
                token_list.append(token)
                # Preserve alias mapping for token → display code
                self._subscriptions[token.upper()] = {"exchange_code": "TOKEN", "product_type": "cash", "alias": (code.upper() or token.upper())}
            elif code:
                regular.append((code, ex, str(it.get("product_type") or "cash")))

        if token_list:
            svc = self._ensure_breeze()
            if not svc:
                raise RuntimeError("No Breeze session available")
            if not self._connected:
                self.connect()
            try:
                svc.client.subscribe_feeds(stock_token=token_list)
                for t in token_list:
                    self._subscriptions[t] = {"exchange_code": "TOKEN", "product_type": "cash"}
            except Exception as exc:
                log_exception(exc, context="BreezeSocketService.subscribe_many.tokens")

        for code, ex, prod in regular:
            try:
                self.subscribe(code, ex, prod)
            except Exception:
                continue

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


