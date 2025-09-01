from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import settings
from .response import log_exception


_ENGINE: Optional[Engine] = None


def get_engine() -> Optional[Engine]:
	global _ENGINE
	if _ENGINE is not None:
		return _ENGINE
	try:
		dsn = settings.postgres_dsn
		if not dsn:
			return None
		_ENGINE = create_engine(dsn, pool_pre_ping=True)
		return _ENGINE
	except Exception as exc:
		log_exception(exc, context="postgres.get_engine")
		return None


@contextmanager
def get_conn():
	engine = get_engine()
	if engine is None:
		yield None
		return
	conn = engine.connect()
	try:
		yield conn
		conn.commit()
	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()


def ensure_tables() -> None:
	"""Create required tables if they do not exist."""
	engine = get_engine()
	if engine is None:
		return
	try:
		with engine.begin() as conn:
			conn.execute(text(
				"""
				CREATE TABLE IF NOT EXISTS quotes_cache (
					symbol TEXT PRIMARY KEY,
					data JSONB NOT NULL,
					updated_at TIMESTAMPTZ NOT NULL
				);

				CREATE TABLE IF NOT EXISTS market_holidays (
					date TEXT PRIMARY KEY,
					name TEXT,
					source TEXT NOT NULL,
					updated_at TIMESTAMPTZ NOT NULL
				);

				-- Backward compatibility: add columns if missing
				ALTER TABLE market_holidays ADD COLUMN IF NOT EXISTS name TEXT;

				CREATE TABLE IF NOT EXISTS api_usage (
					date TEXT NOT NULL,
					method TEXT NOT NULL,
					count BIGINT NOT NULL,
					updated_at TIMESTAMPTZ NOT NULL,
					PRIMARY KEY (date, method)
				);

				-- Historical OHLC cache
				CREATE TABLE IF NOT EXISTS historical_data (
					id BIGSERIAL PRIMARY KEY,
					symbol TEXT NOT NULL,
					date DATE NOT NULL,
					ohlc JSONB NOT NULL,
					UNIQUE(symbol, date)
				);

				-- Backtests summary table
				CREATE EXTENSION IF NOT EXISTS pgcrypto;
				CREATE TABLE IF NOT EXISTS backtests (
					id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
					user_id UUID NOT NULL,
					symbol TEXT NOT NULL,
					strategy TEXT NOT NULL,
					params JSONB,
					start_date DATE,
					end_date DATE,
					summary JSONB,
					created_at TIMESTAMPTZ DEFAULT NOW()
				);

				-- Trades per backtest
				CREATE TABLE IF NOT EXISTS trades (
					id BIGSERIAL PRIMARY KEY,
					backtest_id UUID REFERENCES backtests(id) ON DELETE CASCADE,
					trade_no INT,
					entry_date TIMESTAMPTZ,
					exit_date TIMESTAMPTZ,
					entry_price NUMERIC,
					exit_price NUMERIC,
					pnl NUMERIC,
					pnl_pct NUMERIC
				);

				-- Strategies catalog
				CREATE TABLE IF NOT EXISTS strategies (
					id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
					name TEXT NOT NULL,
					description TEXT,
					json JSONB NOT NULL,
					created_at TIMESTAMPTZ DEFAULT NOW()
				);

				-- Instruments master from ICICI SecurityMaster
				CREATE TABLE IF NOT EXISTS instruments (
					token VARCHAR PRIMARY KEY,
					symbol VARCHAR,
					short_name VARCHAR,
					company_name VARCHAR,
					series VARCHAR,
					isin VARCHAR,
					lot_size VARCHAR,
					exchange VARCHAR,
					last_update TIMESTAMPTZ DEFAULT NOW()
				);

				-- Backward compatibility: add last_update if missing
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS last_update TIMESTAMPTZ DEFAULT NOW();
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS short_name VARCHAR;
				-- Store all original source columns as JSONB for future-proofing
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS raw JSONB;
				-- New fields requested for NSE/BSE mapping
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS exchange_code VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS scrip_id VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS scrip_name VARCHAR;

				-- Nifty 50 list (daily refresh around 08:00 IST)
				CREATE TABLE IF NOT EXISTS nifty50_list (
					id BIGSERIAL PRIMARY KEY,
					symbol VARCHAR NOT NULL,
					stock_code VARCHAR,
					company_name VARCHAR,
					exchange VARCHAR DEFAULT 'NSE',
					weight NUMERIC,
					sector VARCHAR,
					updated_at TIMESTAMPTZ DEFAULT NOW(),
					UNIQUE(symbol, exchange)
				);
				"""
			))
	except Exception as exc:
		log_exception(exc, context="postgres.ensure_tables")


