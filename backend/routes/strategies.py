from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text
import json
import pandas as pd

from ..utils.postgres import get_conn, ensure_tables
from ..utils.response import success_response, error_response, log_exception
from ..services.strategy_schema import Strategy
from ..services.strategy_engine import evaluate_strategy
from ..services.historical_service import get_ohlc_daily
import os


router = APIRouter(prefix="/api", tags=["strategies"])


class StrategyPayload(BaseModel):
	name: str
	description: Optional[str] = None
	strategy_data: Dict[str, Any] = Field(..., alias="json", description="Strategy configuration data")


@router.post("/strategies/")
def create_strategy(payload: StrategyPayload) -> Dict[str, Any]:
	try:
		ensure_tables()
		# Validate strategy JSON
		_ = Strategy.from_dict(payload.strategy_data)
		with get_conn() as conn:
			if conn is None:
				return error_response("Database not configured")
			row = conn.execute(
				text(
					"""
					INSERT INTO strategies (name, description, json)
					VALUES (:name, :description, CAST(:json AS JSONB))
					RETURNING id
					"""
				),
				{"name": payload.name, "description": payload.description, "json": json.dumps(payload.strategy_data)},
			)
			new_id = row.fetchone()[0]
		return success_response("Strategy created", id=str(new_id))
	except Exception as exc:
		log_exception(exc, context="strategies.create")
		return error_response("Failed to create strategy", error=str(exc))


@router.get("/strategies/templates")
def list_strategy_templates() -> Dict[str, Any]:
	try:
		base = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
		items = []
		for fname in ("ma_crossover.json", "rsi_ob_os.json", "breakout.json"):
			path = os.path.join(base, fname)
			if not os.path.exists(path):
				log_exception(Exception(f"Template file not found: {path}"), context="strategies.templates")
				continue
			with open(path, 'r', encoding='utf-8') as fh:
				try:
					items.append(json.load(fh))
				except Exception as e:
					log_exception(e, context="strategies.templates.parse")
					continue
		return {"success": True, "message": "Templates loaded", "items": items, "count": len(items), "base_path": base}
	except Exception as exc:
		log_exception(exc, context="strategies.templates")
		return error_response("Failed to load templates", error=str(exc))


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str) -> Dict[str, Any]:
	try:
		with get_conn() as conn:
			if conn is None:
				return error_response("Database not configured")
			row = conn.execute(text("SELECT id, name, description, json, created_at FROM strategies WHERE id = :id"), {"id": strategy_id}).fetchone()
			if not row:
				return error_response("Strategy not found")
			return success_response("Strategy", strategy={
				"id": str(row[0]),
				"name": row[1],
				"description": row[2],
				"json": row[3],
				"created_at": row[4],
			})
	except Exception as exc:
		log_exception(exc, context="strategies.get")
		return error_response("Failed to fetch strategy", error=str(exc))


class StrategyBacktestPayload(BaseModel):
	strategy: Dict[str, Any] | None = None
	strategy_id: Optional[str] = None
	symbol: str
	start_date: date
	end_date: date


@router.post("/backtest/")
def run_strategy_backtest(payload: StrategyBacktestPayload) -> Dict[str, Any]:
	try:
		# Load strategy either from payload or DB
		if payload.strategy is not None:
			strat = Strategy.from_dict(payload.strategy)
		elif payload.strategy_id:
			with get_conn() as conn:
				if conn is None:
					return error_response("Database not configured")
				row = conn.execute(text("SELECT json FROM strategies WHERE id = :id"), {"id": payload.strategy_id}).fetchone()
				if not row:
					return error_response("Strategy not found")
				strat = Strategy.from_dict(row[0])
		else:
			return error_response("Provide strategy or strategy_id")

		# Fetch OHLC data (daily) for the requested symbol
		bars = get_ohlc_daily(payload.symbol, payload.start_date, payload.end_date)
		if not bars:
			return error_response("No OHLC data available for given range")
		# Convert to DataFrame with at least a 'close' column and index as datetime
		idx = pd.to_datetime([b.date for b in bars])
		close = [b.close for b in bars]
		df = pd.DataFrame({"close": close, "RSI": close}, index=idx)  # placeholder: RSI column expected by example
		# Note: For real use, compute indicators from src/services/indicators.py and add to df

		data = {payload.symbol: df}
		signals_df = evaluate_strategy(strat, data)
		return success_response("Backtest signals", signals=signals_df.to_dict(orient="records"))
	except Exception as exc:
		log_exception(exc, context="strategies.backtest")
		return error_response("Failed to run backtest", error=str(exc))


