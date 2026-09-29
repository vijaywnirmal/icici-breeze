"""The market data the paper engine needs, behind a small interface so tests can supply their own.

Everything comes from Breeze's historical endpoint, so a whole session can be simulated after the close
(or days later): Nifty's daily and 5-minute bars, and an option contract's 1-minute and 1-second bars
(get_historical_data_v2 interval="1second" - it works for NFO options, including expired contracts).
"""
from __future__ import annotations

import datetime as dt
from typing import Protocol

import pandas as pd

COLS = ["Open", "High", "Low", "Close"]
SECOND_CHUNK = dt.timedelta(minutes=15)


class MarketData(Protocol):
    def index_daily(self, start: dt.date, end: dt.date) -> pd.DataFrame:
        """Open/High/Low/Close by date; only sessions that happened."""

    def index_bars(self, start: dt.date, end: dt.date, interval: str) -> pd.DataFrame:
        """Intraday Open/High/Low/Close indexed by bar start time (naive IST datetimes)."""

    def option_bars(self, expiry: dt.date, strike: int, right: str, day: dt.date) -> pd.DataFrame:
        """The contract's 1-minute bars for `day` (empty if it didn't trade / doesn't exist)."""

    def option_seconds(self, expiry: dt.date, strike: int, right: str, start: dt.datetime,
                       end: dt.datetime) -> pd.DataFrame:
        """The contract's 1-second bars in [start, end] (naive IST), empty if unavailable."""


def _stamp(d: dt.date, hhmm: str = "00:00") -> str:
    # Breeze takes IST wall-clock times written with a Z suffix
    return f"{d.isoformat()}T{hhmm}:00.000Z"


def _frame(resp) -> pd.DataFrame:
    rows = []
    for r in (resp or {}).get("Success") or []:
        try:
            t = dt.datetime.strptime(str(r["datetime"])[:19], "%Y-%m-%d %H:%M:%S")
            rows.append((t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])))
        except (KeyError, TypeError, ValueError):
            continue
    df = pd.DataFrame(rows, columns=["time", *COLS]).drop_duplicates("time")
    return df.set_index("time").sort_index()


class BreezeMarket:
    """MarketData from a logged-in BreezeConnect client (backend.utils.session.get_breeze().client)."""

    def __init__(self, client, symbol: str = "NIFTY"):
        self.client = client
        self.symbol = symbol

    def index_daily(self, start, end):
        df = _frame(self.client.get_historical_data_v2(
            interval="1day", from_date=_stamp(start), to_date=_stamp(end, "23:59"),
            stock_code=self.symbol, exchange_code="NSE", product_type="cash"))
        df.index = [t.date() for t in df.index]
        return df

    def index_bars(self, start, end, interval):
        return _frame(self.client.get_historical_data_v2(
            interval=interval, from_date=_stamp(start, "09:00"), to_date=_stamp(end, "15:35"),
            stock_code=self.symbol, exchange_code="NSE", product_type="cash"))

    def option_bars(self, expiry, strike, right, day):
        try:
            return _frame(self.client.get_historical_data_v2(
                interval="1minute", from_date=_stamp(day, "09:15"), to_date=_stamp(day, "15:30"),
                stock_code=self.symbol, exchange_code="NFO", product_type="options",
                expiry_date=_stamp(expiry, "06:00"), right=right, strike_price=str(strike)))
        except Exception:
            return pd.DataFrame(columns=COLS)

    def option_seconds(self, expiry, strike, right, start, end):
        # Breeze returns ~1,000 rows per call at most; 15-minute chunks stay under that (900 seconds)
        parts, t = [], start
        while t <= end:
            stop = min(end, t + SECOND_CHUNK - dt.timedelta(seconds=1))
            try:
                parts.append(_frame(self.client.get_historical_data_v2(
                    interval="1second", from_date=f"{t:%Y-%m-%dT%H:%M:%S}.000Z", to_date=f"{stop:%Y-%m-%dT%H:%M:%S}.000Z",
                    stock_code=self.symbol, exchange_code="NFO", product_type="options",
                    expiry_date=_stamp(expiry, "06:00"), right=right, strike_price=str(strike))))
            except Exception:
                pass
            t = stop + dt.timedelta(seconds=1)
        parts = [p for p in parts if not p.empty]
        if not parts:
            return pd.DataFrame(columns=COLS)
        df = pd.concat(parts)
        return df[~df.index.duplicated()].sort_index()
