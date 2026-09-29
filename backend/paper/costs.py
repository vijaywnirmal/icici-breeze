"""Charges for one options fill, the way an Indian discount broker's contract note adds them up."""
from __future__ import annotations

from .config import PaperConfig


def charges(turnover: float, side: str, cfg: PaperConfig) -> float:
    """Total charges in rupees for one fill of `turnover` (premium x quantity). side: "buy" or "sell"."""
    brokerage = cfg.brokerage_per_order
    exchange = turnover * cfg.exchange_pct / 100
    sebi = turnover * cfg.sebi_per_crore / 1e7
    stt = turnover * cfg.stt_sell_pct / 100 if side == "sell" else 0.0
    stamp = turnover * cfg.stamp_buy_pct / 100 if side == "buy" else 0.0
    gst = (brokerage + exchange + sebi) * cfg.gst_pct / 100
    return round(brokerage + exchange + sebi + stt + stamp + gst, 2)


def slipped(price: float, side: str, cfg: PaperConfig) -> float:
    """Fill price after adverse slippage: pay a bit more to open, get a bit less to close."""
    k = cfg.slippage_pct / 100
    return round(price * (1 + k) if side == "buy" else price * (1 - k), 2)
