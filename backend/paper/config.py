"""Every assumption of the paper trader, in one place.

Defaults follow backend/templates/ma_crossover.json and the MA-crossover defaults in routes/backtests.py,
completed with what the templates leave out (call or put, exits, size). Override any field by writing it
to data/paper/config.json, e.g. {"fast": 10, "slow": 30, "lots": 2}.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "paper"


@dataclass
class PaperConfig:
    # --- signal, decided on Nifty's daily close
    symbol: str = "NIFTY"
    fast: int = 20  # up-trend while the fast average is above the slow one -> hold a call; else a put
    slow: int = 50

    # --- contract
    strike_step: int = 50  # ATM = decision-day close rounded to this
    expiry_weekday: int = 1  # Nifty weeklies expire on Tuesday (0 = Monday)
    lot_size: int = 65  # NSE Nifty lot size - check the current value; it is revised from time to time
    lots: int = 1

    # --- money
    capital: float = 100_000.0  # notional paper rupees

    # --- costs (per fill). Rates as percentages of premium turnover unless stated.
    slippage_pct: float = 0.5  # adverse fill vs the 09:15 print; option spreads are wide at the open
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
