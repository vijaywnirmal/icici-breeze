"""The market data the paper engine needs, behind a small interface so tests can supply their own.

Everything comes from Breeze's historical endpoint, so a day can be priced after the fact:
  - Nifty daily bars (decisions and marking the benchmark)
  - an option's 09:15 opening price (fills) and daily close (marking positions)
"""
from __future__ import annotations

import datetime as dt
from typing import Optional, Protocol

import pandas as pd


class MarketData(Protocol):
    def index_daily(self, start: dt.date, end: dt.date) -> pd.DataFrame:
        """Columns Open/High/Low/Close indexed by date; only sessions that happened."""

    def option_open(self, expiry: dt.date, strike: int, right: str, day: dt.date) -> Optional[float]:
        """First traded price of the contract on `day` (09:15 minute bar), or None if it didn't trade."""

    def option_close(self, expiry: dt.date, strike: int, right: str, day: dt.date) -> Optional[float]:
        """The contract's closing price on `day`, or None."""


def _stamp(d: dt.date, hhmm: str = "00:00") -> str:
    # Breeze takes IST wall-clock times written with a Z suffix
    return f"{d.isoformat()}T{hhmm}:00.000Z"


class BreezeMarket:
    """MarketData from a logged-in BreezeConnect client (backend.utils.session.get_breeze().client)."""

    def __init__(self, client, symbol: str = "NIFTY"):
        self.client = client
        self.symbol = symbol
        self._cache: dict[tuple, Optional[float]] = {}

    def index_daily(self, start: dt.date, end: dt.date) -> pd.DataFrame:
        resp = self.client.get_historical_data_v2(
            interval="1day", from_date=_stamp(start), to_date=_stamp(end, "23:59"),
            stock_code=self.symbol, exchange_code="NSE", product_type="cash")
        rows = []
        for r in (resp or {}).get("Success") or []:
            try:
                d = dt.datetime.strptime(str(r["datetime"])[:10], "%Y-%m-%d").date()
                rows.append((d, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])))
            except (KeyError, TypeError, ValueError):
                continue
        df = pd.DataFrame(rows, columns=["date", "Open", "High", "Low", "Close"]).drop_duplicates("date")
        return df.set_index("date").sort_index()

    def _option(self, interval: str, expiry: dt.date, strike: int, right: str, day: dt.date,
                start: str, end: str, field: str, pick_last: bool) -> Optional[float]:
        key = (interval, expiry, strike, right, day, field)
        if key in self._cache:
            return self._cache[key]
        price = None
        try:
            resp = self.client.get_historical_data_v2(
                interval=interval, from_date=_stamp(day, start), to_date=_stamp(day, end),
                stock_code=self.symbol, exchange_code="NFO", product_type="options",
                expiry_date=_stamp(expiry, "06:00"), right=right, strike_price=str(strike))
            bars = [b for b in (resp or {}).get("Success") or [] if b.get(field) not in (None, "", 0, "0")]
            if bars:
                price = float((bars[-1] if pick_last else bars[0])[field])
        except Exception:
            price = None
        self._cache[key] = price
        return price

    def option_open(self, expiry, strike, right, day):
        return self._option("1minute", expiry, strike, right, day, "09:15", "09:20", "open", pick_last=False)

    def option_close(self, expiry, strike, right, day):
        return self._option("1day", expiry, strike, right, day, "00:00", "23:59", "close", pick_last=True)
