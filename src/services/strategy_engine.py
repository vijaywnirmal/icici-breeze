from __future__ import annotations

from typing import Dict, List, Literal, Optional

import pandas as pd

from .strategy_schema import Strategy, Condition, Action, EXAMPLE_STRATEGY
from .indicators import INDICATOR_REGISTRY


LogicOp = Literal["AND", "OR"]


def _resolve_indicator_value(row: pd.Series, indicator: str) -> Optional[float]:
	"""Return indicator value from row by trying reasonable column name variants."""
	candidates = [indicator, indicator.upper(), indicator.lower(), indicator.capitalize()]
	for col in candidates:
		if col in row.index:
			val = row[col]
			try:
				return float(val) if val is not None else None
			except Exception:
				return None
	return None


def _evaluate_condition(op: str, curr: Optional[float], prev: Optional[float], threshold: Optional[float]) -> bool:
	if curr is None:
		return False
	if op == "<":
		return threshold is not None and curr < threshold
	if op == ">":
		return threshold is not None and curr > threshold
	if op == "crosses_above":
		return prev is not None and threshold is not None and prev <= threshold and curr > threshold
	if op == "crosses_below":
		return prev is not None and threshold is not None and prev >= threshold and curr < threshold
	return False


def _get_timestamps_for_symbols(data: Dict[str, pd.DataFrame], symbols: List[str]) -> List[pd.Timestamp]:
	indices: List[pd.DatetimeIndex] = []
	for sym in symbols:
		df = data.get(sym)
		if df is None or df.empty:
			continue
		if isinstance(df.index, pd.DatetimeIndex):
			idx = df.index
		else:
			# Optional: try to use a 'timestamp' column
			if 'timestamp' in df.columns:
				idx = pd.to_datetime(df['timestamp'])
				df.index = idx
			else:
				continue
		indices.append(df.index)
	if not indices:
		return []
	# Intersect timestamps across referenced symbols to align bar-by-bar
	common = indices[0]
	for idx in indices[1:]:
		common = common.intersection(idx)
	return list(common.sort_values())


def evaluate_strategy(strategy: Strategy, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
	"""Evaluate a declarative strategy on provided OHLCV+indicator data.

	Parameters
	----------
	strategy: Strategy
		Validated strategy schema parsed from JSON.
	data: Dict[str, pd.DataFrame]
		Mapping of symbol -> DataFrame where index is DatetimeIndex and indicator columns
		(e.g., 'RSI', 'SMA') already exist.

	Returns
	-------
	pd.DataFrame
		Signals DataFrame with columns: timestamp, type, signal, instrument, strike, expiry, strategy_name
	"""
	# Determine logic (AND/OR). Defaults to AND if unspecified in schema.
	logic: LogicOp = getattr(strategy, 'logic', 'AND')  # type: ignore[attr-defined]
	logic = 'AND' if logic not in ('AND', 'OR') else logic

	# Gather referenced symbols from conditions
	ref_syms = list({c.symbol for c in strategy.conditions})
	# Timeline to iterate
	timestamps = _get_timestamps_for_symbols(data, ref_syms)
	if not timestamps:
		return pd.DataFrame(columns=[
			"timestamp", "type", "signal", "instrument", "strike", "expiry", "strategy_name"
		])

	signals: List[dict] = []
	# Iterate over time
	for i, ts in enumerate(timestamps):
		cond_results: List[bool] = []
		for cond in strategy.conditions:
			df = data.get(cond.symbol)
			if df is None or df.empty or ts not in df.index:
				cond_results.append(False)
				continue
			row = df.loc[ts]
			prev_row = None
			if i > 0 and timestamps[i-1] in df.index:
				prev_row = df.loc[timestamps[i-1]]
			curr_val = _resolve_indicator_value(row, cond.indicator)
			prev_val = _resolve_indicator_value(prev_row, cond.indicator) if prev_row is not None else None
			# Numeric threshold only; ignore non-numeric (e.g., 'ATM') in condition evaluation layer
			try:
				thr = float(cond.value) if isinstance(cond.value, (int, float, str)) and str(cond.value).replace('.', '', 1).replace('-', '', 1).isdigit() else None
			except Exception:
				thr = None
			ok = _evaluate_condition(cond.operator, curr_val, prev_val, thr)
			cond_results.append(ok)

		all_ok = all(cond_results) if logic == 'AND' else any(cond_results)
		if not all_ok:
			continue
		for act in strategy.actions:
			signals.append({
				"timestamp": ts,
				"type": act.type,
				"signal": act.signal,
				"instrument": act.instrument,
				"strike": act.strike,
				"expiry": act.expiry,
				"strategy_name": strategy.name,
			})

	if not signals:
		return pd.DataFrame(columns=[
			"timestamp", "type", "signal", "instrument", "strike", "expiry", "strategy_name"
		])

	df_sig = pd.DataFrame(signals)
	df_sig.sort_values("timestamp", inplace=True)
	df_sig.reset_index(drop=True, inplace=True)
	return df_sig


# --- Example test harness ---
def _build_example_data() -> Dict[str, pd.DataFrame]:
	idx = pd.to_datetime([
		"2024-01-01 09:15:00",
		"2024-01-01 09:20:00",
		"2024-01-01 09:25:00",
	])
	df_nifty = pd.DataFrame({
		"RSI": [30.0, 18.0, 25.0],
	}, index=idx)
	df_opt = pd.DataFrame({
		"RSI": [35.0, 19.0, 28.0],
	}, index=idx)
	return {"NIFTY": df_nifty, "NIFTY_OPTIONS": df_opt}


def _example_strategy_and() -> Strategy:
	from .strategy_schema import Strategy
	return Strategy.from_dict(EXAMPLE_STRATEGY)


def _run_example() -> pd.DataFrame:
	data = _build_example_data()
	strat = _example_strategy_and()
	return evaluate_strategy(strat, data)


if __name__ == "__main__":
	df = _run_example()
	print(df)


