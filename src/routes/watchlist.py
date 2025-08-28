from __future__ import annotations

from typing import Any, Dict, List, Tuple
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..models.watchlist import WatchItem, Watchlist
from ..utils.response import success_response, error_response


router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# In-memory store keyed by user_id -> Watchlist
# TODO: Replace with a persistent DB keyed by authenticated user/session
_STORE: Dict[str, Watchlist] = {}


class ReorderPayload(BaseModel):
	order: List[str] = Field(..., description="Array of symbols in desired order")


class AlertsPayload(BaseModel):
	symbol: str
	exchange_code: str = 'NSE'
	product_type: str = 'cash'
	alert_up_pct: float | None = None
	alert_down_pct: float | None = None


def get_user_id() -> str:
	# TODO: Replace with real session/user extraction from auth
	return "demo-user"


@router.get("")
def get_watchlist(user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
	wl = _STORE.get(user_id)
	if wl is None:
		wl = Watchlist()
		_STORE[user_id] = wl
	return success_response("OK", watchlist=wl.model_dump())


@router.post("/items")
def add_item(item: WatchItem, user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
	wl = _STORE.get(user_id) or Watchlist()

	# Dedupe by (symbol, exchange_code, product_type)
	key: Tuple[str, str, str] = (item.symbol.upper(), item.exchange_code, item.product_type)
	existing = [
		(idx, it)
		for idx, it in enumerate(wl.items)
		if (it.symbol.upper(), it.exchange_code, it.product_type) == key
	]
	if existing:
		# Update display_name if provided; keep existing order
		idx, it = existing[0]
		if item.display_name:
			wl.items[idx] = WatchItem(**{**it.model_dump(), "display_name": item.display_name})
	else:
		wl.items.append(item)

	_STORE[user_id] = wl
	return success_response("Item added", watchlist=wl.model_dump())


@router.delete("/items")
def remove_item(item: WatchItem, user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
	wl = _STORE.get(user_id) or Watchlist()
	key: Tuple[str, str, str] = (item.symbol.upper(), item.exchange_code, item.product_type)
	wl.items = [
		it for it in wl.items
		if (it.symbol.upper(), it.exchange_code, it.product_type) != key
	]
	_STORE[user_id] = wl
	return success_response("Item removed", watchlist=wl.model_dump())


@router.patch("/order")
def reorder(payload: ReorderPayload, user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
	wl = _STORE.get(user_id) or Watchlist()
	order = [s.upper() for s in payload.order]
	# Stable partition by provided symbol order; keep others at the end
	order_index = {sym: i for i, sym in enumerate(order)}
	wl.items.sort(key=lambda it: (order_index.get(it.symbol.upper(), 10**9), it.symbol))
	_STORE[user_id] = wl
	return success_response("Order updated", watchlist=wl.model_dump())


@router.patch("/items/alerts")
def set_alerts(payload: AlertsPayload, user_id: str = Depends(get_user_id)) -> Dict[str, Any]:
	wl = _STORE.get(user_id) or Watchlist()
	key = (payload.symbol.upper(), payload.exchange_code, payload.product_type)
	found = False
	for idx, it in enumerate(wl.items):
		if (it.symbol.upper(), it.exchange_code, it.product_type) == key:
			data = it.model_dump()
			data["alert_up_pct"] = payload.alert_up_pct
			data["alert_down_pct"] = payload.alert_down_pct
			wl.items[idx] = WatchItem(**data)
			found = True
			break
	if not found:
		return error_response("Symbol not in watchlist", error="not_found")

	_STORE[user_id] = wl
	# TODO: evaluate thresholds on incoming ticks in streaming services
	return success_response("Alerts updated", watchlist=wl.model_dump())
