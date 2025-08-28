from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from ..models.watchlist import Watchlist
from ..routes.watchlist import _STORE, get_user_id  # reuse in-memory store
from ..services.watchlist_data import WatchlistWSService
from ..services.breeze_service import BreezeService
from ..utils.response import log_exception


router = APIRouter(tags=["watchlist-stream"])  # absolute ws path


@router.websocket("/ws/watchlist")
async def ws_watchlist(websocket: WebSocket, user_id: str = Depends(get_user_id)) -> None:
	await websocket.accept()

	# Resolve symbols from current watchlist
	wl: Watchlist = _STORE.get(user_id) or Watchlist()
	symbols: List[str] = [it.symbol for it in wl.items] or ["NIFTY"]
	service = WatchlistWSService(symbols=symbols, min_send_interval_ms=250, poll_interval_s=45)

	# Attach Breeze client (in real app, reuse user's authenticated Breeze session)
	service.attach_breeze(BreezeService(api_key=""))  # placeholder

	async def send_text(obj: Dict[str, Any]) -> None:
		try:
			await websocket.send_text(json.dumps(obj))
		except Exception as exc:
			log_exception(exc, context="ws_watchlist.send_text")

	await service.start(send_text)

	try:
		while True:
			# For MVP we do not require client messages; just keep the connection
			await asyncio.sleep(1)
	except WebSocketDisconnect:
		pass
	except Exception as exc:
		log_exception(exc, context="ws_watchlist.loop")
	finally:
		with contextlib.suppress(Exception):
			await service.stop()
		with contextlib.suppress(Exception):
			await websocket.close()
