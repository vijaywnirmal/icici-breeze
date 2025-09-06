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
				-- LTP Cache for both indexes and stocks (renamed from quotes_cache)
				CREATE TABLE IF NOT EXISTS ltp_cache (
					symbol TEXT PRIMARY KEY,
					ltp NUMERIC,
					close NUMERIC,
					change_pct NUMERIC,
					bid NUMERIC,
					ask NUMERIC,
					volume BIGINT,
					data JSONB,
					updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
				);

				-- Backward compatibility: rename quotes_cache to ltp_cache if it exists
				DO $$ 
				BEGIN
					IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'quotes_cache') THEN
						ALTER TABLE quotes_cache RENAME TO ltp_cache;
						-- Add new columns if they don't exist
						ALTER TABLE ltp_cache ADD COLUMN IF NOT EXISTS ltp NUMERIC;
						ALTER TABLE ltp_cache ADD COLUMN IF NOT EXISTS close NUMERIC;
						ALTER TABLE ltp_cache ADD COLUMN IF NOT EXISTS change_pct NUMERIC;
						ALTER TABLE ltp_cache ADD COLUMN IF NOT EXISTS bid NUMERIC;
						ALTER TABLE ltp_cache ADD COLUMN IF NOT EXISTS ask NUMERIC;
						ALTER TABLE ltp_cache ADD COLUMN IF NOT EXISTS volume BIGINT;
					END IF;
				END $$;

				-- Add indexes for ltp_cache performance
				CREATE INDEX IF NOT EXISTS idx_ltp_cache_updated_at ON ltp_cache(updated_at);
				CREATE INDEX IF NOT EXISTS idx_ltp_cache_symbol ON ltp_cache(symbol);




				-- Historical OHLC cache
				CREATE TABLE IF NOT EXISTS historical_data (
					id BIGSERIAL PRIMARY KEY,
					symbol TEXT NOT NULL,
					date DATE NOT NULL,
					ohlc JSONB NOT NULL,
					UNIQUE(symbol, date)
				);

				-- Market holidays table
				CREATE TABLE IF NOT EXISTS market_holidays (
					date DATE PRIMARY KEY,
					day TEXT NOT NULL,
					name TEXT NOT NULL
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
					websocket_enabled BOOLEAN DEFAULT FALSE,
					last_update TIMESTAMPTZ DEFAULT NOW()
				);

				-- Backward compatibility: add columns if missing
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS last_update TIMESTAMPTZ DEFAULT NOW();
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS symbol VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS isin VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS exchange VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS short_name VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS websocket_enabled BOOLEAN DEFAULT FALSE;
				-- Store all original source columns as JSONB for future-proofing
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS raw JSONB;
				-- New fields requested for NSE/BSE mapping
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS exchange_code VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS scrip_id VARCHAR;
				ALTER TABLE instruments ADD COLUMN IF NOT EXISTS scrip_name VARCHAR;

				-- Add indexes for performance
				CREATE INDEX IF NOT EXISTS idx_instruments_websocket_enabled ON instruments(websocket_enabled);

				"""
			))
	except Exception as exc:
		log_exception(exc, context="postgres.ensure_tables")


