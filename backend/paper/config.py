"""Every assumption of the intraday options paper trader, in one place.

The signal is backend/templates/rsi_ob_os.json (Nifty 5-minute RSI below 20), completed with what the
template leaves out: the mirror-image put at RSI above 80, which contract, when to close, and size.
Override any field by writing it to data/paper/config.json, e.g. {"target_pct": 40, "lots": 2}.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "paper"


@dataclass
class PaperConfig:
    # --- signal: Nifty 5-minute RSI
    symbol: str = "NIFTY"
    bar_interval: str = "5minute"
    rsi_period: int = 14
    oversold: float = 20.0  # RSI below this -> ATM call
    overbought: float = 80.0  # RSI above this -> ATM put
    first_entry: str = "09:30"  # skip the opening auction noise
    last_entry: str = "14:30"  # no new trades this late
    max_trades_per_day: int = 1

    # --- contract: at-the-money, nearest weekly expiry after today (never an expiry-day contract)
    strike_step: int = 50
    expiry_weekday: int = 1  # Nifty weeklies expire on Tuesday (0 = Monday)
    lot_size: int = 65  # NSE Nifty lot size - check the current value; it is revised from time to time
    lots: int = 1

    # --- closing: whichever comes first
    target_pct: float = 30.0  # premium up this much from the fill
    stop_pct: float = 20.0  # premium down this much from the fill
    square_off: str = "15:15"  # close whatever is open

    # --- money
    capital: float = 100_000.0  # notional paper rupees

    # --- costs (per fill). Rates are percentages of premium turnover unless stated.
    slippage_pct: float = 0.5  # adverse, on market fills (entry, stop, square-off); targets fill at the limit
    brokerage_per_order: float = 20.0
    stt_sell_pct: float = 0.1  # STT on options is charged on the sell side premium
    exchange_pct: float = 0.03503  # NSE transaction charge on options premium
    sebi_per_crore: float = 10.0
    stamp_buy_pct: float = 0.003
    gst_pct: float = 18.0  # on brokerage + exchange + SEBI fees

    def as_dict(self) -> dict:
        return asdict(self)


def load_config() -> PaperConfig:
    cfg = PaperConfig()
    path = DATA_DIR / "config.json"
    try:
        overrides = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cfg
    names = {f.name for f in fields(PaperConfig)}
    for k, v in overrides.items():
        if k in names:
            setattr(cfg, k, type(getattr(cfg, k))(v))
    return cfg
