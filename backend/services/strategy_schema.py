from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


Timeframe = str  # e.g., "5m", "15m", "1h", "1d"
Operator = Literal["<", ">", "crosses_above", "crosses_below"]
ActionType = Literal["signal", "trade"]
TradeSignal = Literal["BUY", "SELL"]
ExpiryType = Literal["weekly", "monthly"]


class Condition(BaseModel):
	"""Atomic boolean condition to evaluate on a stream/series.

	Examples:
	- indicator: "RSI", symbol: "NIFTY", timeframe: "5m", operator: "<", value: 20
	- indicator: "SMA", symbol: "NIFTY", timeframe: "1d", operator: "crosses_above", value: 50
	"""

	indicator: str = Field(..., description="Indicator name, e.g., RSI, SMA, EMA")
	symbol: str = Field(..., description="Instrument/symbol to evaluate, e.g., NIFTY")
	timeframe: Timeframe = Field(
		...,
		description="Bar timeframe such as 1m/5m/15m/1h/1d",
		pattern=r"^\d+(s|m|h|d|w)$",
	)
	operator: Operator
	value: Union[float, str] = Field(
		...,
		description="Threshold value (e.g., 20) or keyword like 'ATM'",
	)


class Action(BaseModel):
	"""Instruction to execute when conditions are satisfied."""

	type: ActionType = Field(..., description="Action category: signal or trade")
	signal: TradeSignal = Field(..., description="BUY or SELL")
	instrument: str = Field(..., description="Underlying instrument type, e.g., OPTION, FUTURES")
	strike: str = Field(..., description="Strike selector, e.g., ATM, OTM+1, ITM-2")
	expiry: ExpiryType = Field(..., description="weekly or monthly")


class Strategy(BaseModel):
	"""Declarative strategy definition for the no-code builder."""

	name: str
	description: Optional[str] = None
	universe: List[str] = Field(default_factory=list, description="Universe of tradable instruments")
	conditions: List[Condition] = Field(default_factory=list)
	actions: List[Action] = Field(default_factory=list)

	# --- JSON helpers ---
	def to_json(self, indent: int = 2) -> str:
		"""Serialize the strategy to JSON string.

		Supports Pydantic v1 and v2.
		"""
		if hasattr(self, "model_dump_json"):
			# Pydantic v2
			return self.model_dump_json(indent=indent)
		# Pydantic v1
		return self.json(indent=indent)

	@classmethod
	def from_json(cls, raw: str) -> "Strategy":
		"""Create a Strategy from JSON string (validated)."""
		if hasattr(cls, "model_validate_json"):
			# Pydantic v2
			return cls.model_validate_json(raw)
		# Pydantic v1
		return cls.parse_raw(raw)

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "Strategy":
		if hasattr(cls, "model_validate"):
			# Pydantic v2
			return cls.model_validate(data)
		# Pydantic v1
		return cls.parse_obj(data)

	def to_dict(self) -> Dict[str, Any]:
		if hasattr(self, "model_dump"):
			# Pydantic v2
			return self.model_dump()
		# Pydantic v1
		return self.dict()


# --- Example strategy JSON ---
EXAMPLE_STRATEGY: Dict[str, Any] = {
	"name": "RSI Oversold Option Buy",
	"description": "If RSI < 20 on NIFTY and on ATM option, then BUY the option (weekly).",
	"universe": ["NIFTY", "NIFTY_OPTIONS"],
	"conditions": [
		{"indicator": "RSI", "symbol": "NIFTY", "timeframe": "5m", "operator": "<", "value": 20},
		{"indicator": "RSI", "symbol": "NIFTY_OPTIONS", "timeframe": "5m", "operator": "<", "value": 20},
	],
	"actions": [
		{ "type": "trade", "signal": "BUY", "instrument": "OPTION", "strike": "ATM", "expiry": "weekly" }
	],
}

EXAMPLE_STRATEGY_JSON: str = json.dumps(EXAMPLE_STRATEGY, indent=2)


