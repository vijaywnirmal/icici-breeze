from __future__ import annotations

from typing import TypedDict, NotRequired


class QuotePayload(TypedDict, total=False):
	symbol: str
	status: str
	ltp: float | None
	close: float | None
	change_pct: float | None
	bid: float | None
	ask: float | None
	timestamp: str
	reset: bool


class BacktestTradeDict(TypedDict):
	trade_no: int
	entry_date: str | None
	exit_date: str | None
	entry_price: float | None
	exit_price: float | None
	pnl: float | None
	pnl_pct: float | None


class HistoricalItem(TypedDict):
	date: str
	open: float
	high: float
	low: float
	close: float
	volume: NotRequired[float | None]


