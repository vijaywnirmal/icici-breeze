from __future__ import annotations

from typing import Callable, Dict, Optional

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int = 20) -> pd.Series:
	return series.rolling(window=period, min_periods=period).mean()


def ema(series: pd.Series, period: int = 20) -> pd.Series:
	return series.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
	# Wilder's RSI
	delta = series.diff()
	gain = delta.clip(lower=0.0)
	loss = -delta.clip(upper=0.0)
	avg_gain = gain.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
	avg_loss = loss.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
	rs = avg_gain / avg_loss.replace(0, np.nan)
	rsi_val = 100.0 - (100.0 / (1.0 + rs))
	return rsi_val


def bollinger(series: pd.Series, period: int = 20, std_mult: float = 2.0, band: str = "middle") -> pd.Series:
	middle = sma(series, period=period)
	std = series.rolling(window=period, min_periods=period).std(ddof=0)
	upper = middle + std_mult * std
	lower = middle - std_mult * std
	band_l = band.lower()
	if band_l == "upper":
		return upper
	if band_l == "lower":
		return lower
	return middle


def atr(df_or_close: pd.Series, period: int = 14, high: Optional[pd.Series] = None, low: Optional[pd.Series] = None, close: Optional[pd.Series] = None) -> pd.Series:
	"""Average True Range. Accepts either a DataFrame with high/low/close columns
	or explicit high/low/close series via kwargs.
	"""
	if isinstance(df_or_close, pd.DataFrame):
		high_s = df_or_close[[c for c in df_or_close.columns if c.lower() == 'high'][0]]
		low_s = df_or_close[[c for c in df_or_close.columns if c.lower() == 'low'][0]]
		close_s = df_or_close[[c for c in df_or_close.columns if c.lower() == 'close'][0]]
	else:
		high_s = high
		low_s = low
		close_s = close if close is not None else df_or_close
	if high_s is None or low_s is None or close_s is None:
		# Not enough data to compute ATR; return NaNs
		return pd.Series(index=(df_or_close.index if hasattr(df_or_close, 'index') else None), dtype=float)
	prev_close = close_s.shift(1)
	tr1 = high_s - low_s
	tr2 = (high_s - prev_close).abs()
	tr3 = (low_s - prev_close).abs()
	tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
	atr_val = tr.ewm(alpha=1.0/period, min_periods=period, adjust=False).mean()
	return atr_val


INDICATOR_REGISTRY: Dict[str, Callable[..., pd.Series]] = {
	"SMA": sma,
	"EMA": ema,
	"RSI": rsi,
	"BOLL": bollinger,
	"BOLLINGER": bollinger,
	"ATR": atr,
}


