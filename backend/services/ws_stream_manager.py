from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Set
import re
import time

from ..utils.response import log_exception
from ..utils.config import settings
from ..utils.session import get_breeze
from .breeze_service import BreezeService
from .quotes_cache import upsert_quote


class BreezeSocketService:
    """Singleton manager for a single Breeze WS connection and fan-out to clients."""

    def __init__(self) -> None:
        self._breeze: Optional[BreezeService] = None
        self._connected = False
        self._clients: Set[Any] = set()
        self._option_clients: Set[Any] = set()  # Separate clients for options
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
                    # Debug logging removed for cleanliness
                    
                    # Normalize minimal payload
                    # Prefer stock_code for options to build consistent alias keys
                    raw_sym = ticks.get("stock_code") or ticks.get("symbol") or ""
                    raw_sym_u = str(raw_sym).upper()
                    # Normalize common index names to canonical codes used by frontend
                    base_sym = raw_sym_u
                    try:
                        if "NIFTY" in raw_sym_u and "BANK" not in raw_sym_u and "FIN" not in raw_sym_u:
                            base_sym = "NIFTY"
                        elif "BANK" in raw_sym_u and "NIFTY" in raw_sym_u:
                            base_sym = "BANKNIFTY"
                        elif "FIN" in raw_sym_u and "NIFTY" in raw_sym_u:
                            base_sym = "FINNIFTY"
                    except Exception:
                        base_sym = raw_sym_u
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
                            # Format expiry date consistently for alias mapping
                            from datetime import datetime
                            try:
                                if isinstance(expiry_raw, str):
                                    # Try to parse different date formats
                                    for fmt in ["%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S.%fZ"]:
                                        try:
                                            parsed_date = datetime.strptime(expiry_raw, fmt)
                                            # Keep only date part as ISO and append the fixed Z time part the API returns
                                            formatted_expiry = parsed_date.strftime("%Y-%m-%dT06:00:00.000Z")
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        # If no format matches, try to extract date part
                                        formatted_expiry = str(expiry_raw)
                                else:
                                    formatted_expiry = str(expiry_raw)
                            except:
                                formatted_expiry = str(expiry_raw)
                            
                            # Normalize strike to int to match frontend
                            try:
                                strike_norm = int(float(strike_raw))
                            except Exception:
                                strike_norm = strike_raw
                            alias_from_tick = f"{base_sym}|{formatted_expiry}|{right_txt}|{strike_norm}"
                            
                            # Debug logging for option chain data (commented out to reduce terminal noise)
                            # if raw_sym_u and raw_sym_u.upper() in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
                            #     print(f"🔍 Option Chain Debug: {raw_sym_u}|{formatted_expiry}|{right_txt}|{strike_raw}")
                            #     print(f"   Raw expiry: {expiry_raw}, Strike: {strike_raw}, Right: {right_raw}")
                    except Exception:
                        alias_from_tick = None

                    symbol = alias_from_tick or alias or base_sym or raw_token_u
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
                        # Duplicate as 'right' so frontend fallback logic can work without alias
                        "right": ticks.get("right") or ticks.get("right_type") or ticks.get("option_type"),
                        "ltp": ticks.get("last") or ticks.get("ltp") or ticks.get("close") or ticks.get("open"),
                        "close": ticks.get("close"),
                        "bid": ticks.get("bPrice") or ticks.get("best_bid_price"),
                        "ask": ticks.get("sPrice") or ticks.get("best_ask_price"),
                        "change_pct": ticks.get("change") or ticks.get("pChange"),
                        "timestamp": ticks.get("ltt") or ticks.get("datetime") or ticks.get("timestamp"),
                        # Add option chain specific fields
                        "volume": ticks.get("ltq") or ticks.get("volume") or ticks.get("total_quantity_traded"),
                        "open_interest": ticks.get("OI") or ticks.get("open_interest") or ticks.get("oi"),
                        "ttv": ticks.get("ttv"),  # Total Trade Volume for OI calculation
                        "last": ticks.get("last") or ticks.get("ltp"),
                        # Market depth (if enabled)
                        "bids": ticks.get("bids") or ticks.get("best_bids") or ticks.get("market_depth_buy"),
                        "asks": ticks.get("asks") or ticks.get("best_asks") or ticks.get("market_depth_sell"),
                        "best_bid_qty": ticks.get("bQty") or ticks.get("best_bid_qty"),
                        "best_ask_qty": ticks.get("sQty") or ticks.get("best_ask_qty"),
                    }

                    # Normalize Breeze 'depth' structure (BestBuyRate-1/BestSellRate-1 ...)
                    try:
                        depth_rows = ticks.get("depth")
                        if isinstance(depth_rows, list) and depth_rows:
                            bids_list: list[dict[str, float]] = []
                            asks_list: list[dict[str, float]] = []
                            
                            # Process each depth level (1-5)
                            for i in range(1, 6):
                                key_buy_px = f"BestBuyRate-{i}"
                                key_buy_qty = f"BestBuyQty-{i}"
                                key_sell_px = f"BestSellRate-{i}"
                                key_sell_qty = f"BestSellQty-{i}"
                                
                                # Find the row that contains this level's data
                                for row in depth_rows:
                                    if key_buy_px in row or key_buy_qty in row:
                                        px = row.get(key_buy_px)
                                        qty = row.get(key_buy_qty)
                                        if px is not None and qty is not None:
                                            bids_list.append({"price": px, "qty": qty})
                                    if key_sell_px in row or key_sell_qty in row:
                                        px = row.get(key_sell_px)
                                        qty = row.get(key_sell_qty)
                                        if px is not None and qty is not None:
                                            asks_list.append({"price": px, "qty": qty})
                            
                            # Sort bids (highest first) and asks (lowest first)
                            bids_list.sort(key=lambda x: x["price"], reverse=True)
                            asks_list.sort(key=lambda x: x["price"])
                            
                            if bids_list:
                                payload["bids"] = bids_list
                            if asks_list:
                                payload["asks"] = asks_list
                                
                            # Silenced verbose market depth debug output
                    except Exception as exc:
                        # Swallow depth parsing errors silently to avoid terminal noise
                        pass
                    # Upsert cache for last-known values (used when market is closed)
                    try:
                        upsert_quote(symbol, payload)
                    except Exception:
                        pass

                    if self._loop is not None:
                        # Check if this is an option tick - treat as option if it has strike and right
                        has_strike = ticks.get("strike_price") is not None or ticks.get("strike") is not None
                        has_right = ticks.get("right_type") is not None or ticks.get("right") is not None or ticks.get("option_type") is not None
                        is_option_tick = has_strike and has_right
                        
                        # Debug logging removed for cleanliness
                        
                        if is_option_tick:
                            # Route to option clients only; filter by each client's selected expiry if provided
                            asyncio.run_coroutine_threadsafe(self._broadcast_options(payload), self._loop)
                            
                            # Also call option tick handlers if they exist
                            option_handlers = getattr(self, '_option_tick_handlers', [])
                            for handler in option_handlers:
                                try:
                                    asyncio.run_coroutine_threadsafe(handler(payload), self._loop)
                                except Exception as exc:
                                    # Swallow handler errors to avoid noisy logs
                                    pass
                        else:
                            # Route to regular clients only
                            asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)
                except Exception as exc:
                    log_exception(exc, context="BreezeSocketService.on_ticks")

            svc.client.on_ticks = on_ticks
            # Now open the websocket connection with retries
            max_attempts = 5
            backoff_seconds = 1.5
            for attempt in range(1, max_attempts + 1):
                try:
                    svc.client.ws_connect()
                    self._connected = True
                    break
                except Exception as ws_exc:
                    log_exception(ws_exc, context="BreezeSocketService.ws_connect", attempt=attempt)
                    if attempt == max_attempts:
                        raise
                    time.sleep(backoff_seconds * attempt)
        except Exception as exc:
            log_exception(exc, context="BreezeSocketService.connect")
            raise

    def subscribe_option(self, stock_code: str, exchange_code: str, expiry_date: str, strike_price: str, right: str, product_type: str) -> None:
        """Subscribe to option chain exchange quotes only."""
        svc = self._ensure_breeze()
        if not svc:
            raise RuntimeError("No Breeze session available")
        if not self._connected:
            self.connect()
        
        try:
            # Subscribe using Breeze API for exchange quotes only
            # Important: omit interval for real-time exchange quotes; passing
            # an interval throttles updates to bar cadence (e.g., 1minute)
            resp = svc.client.subscribe_feeds(
                exchange_code=exchange_code,
                stock_code=stock_code,
                expiry_date=expiry_date,
                strike_price=strike_price,
                right=right,
                product_type=product_type,
                get_market_depth=False,
                get_exchange_quotes=True
            )
            # Silence verbose subscription responses
            
            # Create alias for mapping (match frontend alias exactly)
            # Normalize expiry to ISO for alias; keep original format for API
            from datetime import datetime
            iso_expiry = str(expiry_date)
            try:
                if isinstance(expiry_date, str):
                    # Common inputs: "13-Feb-2025", "2025-09-10T06:00:00.000Z", "2025-09-10"
                    parsed = None
                    for fmt in ("%d-%b-%Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
                        try:
                            parsed = datetime.strptime(expiry_date, fmt)
                            break
                        except ValueError:
                            continue
                    if parsed:
                        iso_expiry = parsed.strftime("%Y-%m-%dT06:00:00.000Z")
                    else:
                        # If it already contains 'T', assume ISO-like
                        iso_expiry = expiry_date
            except Exception:
                iso_expiry = str(expiry_date)

            right_u = right.upper()
            right_txt = "CALL" if right_u in ("CE", "CALL") else "PUT"
            strike_norm = int(float(strike_price))
            alias_iso = f"{stock_code.upper()}|{iso_expiry}|{right_txt}|{strike_norm}"
            alias_raw = f"{stock_code.upper()}|{expiry_date}|{right_txt}|{strike_norm}"
            
            # Store subscription for alias mapping (key by ALIAS and by EXPIRY+RIGHT+STRIKE)
            for alias in (alias_iso, alias_raw, f"{stock_code.upper()}|{iso_expiry}|{right_txt}|{strike_norm}"):
                self._subscriptions[alias] = {
                    "exchange_code": exchange_code,
                    "product_type": product_type,
                    "alias": alias,
                    "stock_code": stock_code,
                    "expiry_date": iso_expiry,
                    "strike_price": strike_norm,
                    "right": right
                }
            
        except Exception as exc:
            log_exception(exc, context="BreezeSocketService.subscribe_option", 
                         stock_code=stock_code, strike_price=strike_price, right=right)
            raise

    def subscribe_option_market_depth(self, stock_code: str, exchange_code: str, expiry_date: str, strike_price: str, right: str, product_type: str) -> None:
        """Subscribe to option chain market depth only."""
        svc = self._ensure_breeze()
        if not svc:
            raise RuntimeError("No Breeze session available")
        if not self._connected:
            self.connect()
        
        try:
            # Subscribe using Breeze API for market depth only
            resp = svc.client.subscribe_feeds(
                exchange_code=exchange_code,
                stock_code=stock_code,
                expiry_date=expiry_date,
                strike_price=strike_price,
                right=right,
                product_type=product_type,
                get_market_depth=True,
                get_exchange_quotes=False
            )
            # Silence verbose subscription responses
            
            # Create alias for mapping (match frontend alias exactly)
            # Normalize expiry to ISO for alias; keep original format for API
            from datetime import datetime
            iso_expiry = str(expiry_date)
            try:
                if isinstance(expiry_date, str):
                    # Common inputs: "13-Feb-2025", "2025-09-10T06:00:00.000Z", "2025-09-10"
                    parsed = None
                    for fmt in ("%d-%b-%Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
                        try:
                            parsed = datetime.strptime(expiry_date, fmt)
                            break
                        except ValueError:
                            continue
                    if parsed:
                        iso_expiry = parsed.strftime("%Y-%m-%dT06:00:00.000Z")
                    else:
                        # If it already contains 'T', assume ISO-like
                        iso_expiry = expiry_date
            except Exception:
                iso_expiry = str(expiry_date)

            right_u = right.upper()
            right_txt = "CALL" if right_u in ("CE", "CALL") else "PUT"
            strike_norm = int(float(strike_price))
            alias_iso = f"{stock_code.upper()}|{iso_expiry}|{right_txt}|{strike_norm}"
            alias_raw = f"{stock_code.upper()}|{expiry_date}|{right_txt}|{strike_norm}"
            
            # Store subscription for alias mapping (key by ALIAS and by EXPIRY+RIGHT+STRIKE)
            # Use same alias format as regular subscriptions but mark as market_depth
            for alias in (alias_iso, alias_raw, f"{stock_code.upper()}|{iso_expiry}|{right_txt}|{strike_norm}"):
                self._subscriptions[alias] = {
                    "exchange_code": exchange_code,
                    "product_type": product_type,
                    "alias": alias,
                    "stock_code": stock_code,
                    "expiry_date": iso_expiry,
                    "strike_price": strike_norm,
                    "right": right,
                    "subscription_type": "market_depth"
                }
            
        except Exception as exc:
            log_exception(exc, context="BreezeSocketService.subscribe_option_market_depth", 
                         stock_code=stock_code, strike_price=strike_price, right=right)
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
            if raw_token and not isinstance(raw_token, bool) and str(raw_token) not in ("", "undefined", "null"):
                try:
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
                except Exception as exc:
                    log_exception(exc, context="BreezeSocketService.subscribe_many.token_processing", token=raw_token)
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
            except IndexError as exc:
                log_exception(exc, context="BreezeSocketService.subscribe_many.tokens.index_error", tokens=token_list)
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
                        get_market_depth=True,
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

    def register_client(self, ws: Any, loop: asyncio.AbstractEventLoop | None = None, is_option_client: bool = False) -> None:
        if loop is not None:
            self._loop = loop
        if is_option_client:
            self._option_clients.add(ws)
        else:
            self._clients.add(ws)

    def unregister_client(self, ws: Any) -> None:
        try:
            self._clients.discard(ws)
            self._option_clients.discard(ws)
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

    async def _broadcast_options(self, payload: Dict[str, Any]) -> None:
        """Broadcast only to option clients."""
        data = json.dumps(payload)
        coros = []
        for ws in list(self._option_clients):
            try:
                coros.append(ws.send_text(data))
            except Exception:
                # Drop dead clients lazily
                self._option_clients.discard(ws)
        if coros:
            try:
                await asyncio.gather(*coros, return_exceptions=True)
            except Exception:
                pass

    def unsubscribe_all_options(self) -> None:
        """Unsubscribe all option-related subscriptions."""
        svc = self._breeze
        if not svc:
            return
        
        option_subs = {k: v for k, v in self._subscriptions.items() 
                      if v.get("product_type") == "options"}
        
        for alias, sub in option_subs.items():
            try:
                svc.client.unsubscribe_feeds(
                    exchange_code=sub.get("exchange_code", "NFO"),
                    stock_code=sub.get("stock_code", "NIFTY"),
                    expiry_date=sub.get("expiry_date"),
                    strike_price=sub.get("strike_price"),
                    right=sub.get("right"),
                    product_type="options",
                    get_market_depth=False,
                    get_exchange_quotes=True
                )
            except Exception as exc:
                log_exception(exc, context="BreezeSocketService.unsubscribe_all_options", alias=alias)
            finally:
                self._subscriptions.pop(alias, None)

    def unsubscribe_options_except(self, expiry_date_iso: str) -> None:
        """Unsubscribe option subs for expiries other than expiry_date_iso (YYYY-MM-DD)."""
        svc = self._breeze
        if not svc:
            return
        keep = (expiry_date_iso or '').strip()[:10]
        option_subs = {k: v for k, v in self._subscriptions.items() if v.get("product_type") == "options"}
        for alias, sub in option_subs.items():
            exp = (sub.get("expiry_date") or '').strip()
            exp10 = exp[:10]
            if exp10 and exp10 == keep:
                continue
            try:
                svc.client.unsubscribe_feeds(
                    exchange_code=sub.get("exchange_code", "NFO"),
                    stock_code=sub.get("stock_code", "NIFTY"),
                    expiry_date=sub.get("expiry_date"),
                    strike_price=sub.get("strike_price"),
                    right=sub.get("right"),
                    product_type="options",
                    get_market_depth=False,
                    get_exchange_quotes=True
                )
            except Exception as exc:
                log_exception(exc, context="BreezeSocketService.unsubscribe_options_except", alias=alias)
            finally:
                self._subscriptions.pop(alias, None)


STREAM_MANAGER = BreezeSocketService()