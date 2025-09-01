import json
import sys
from dotenv import load_dotenv

load_dotenv()

from src.utils.postgres import get_engine  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

EXPECTED_TABLES = [
    "quotes_cache",
    "market_holidays",
    "api_usage",
    "historical_data",
    "backtests",
    "trades",
    "strategies",
    "instruments",
    "nifty50_list",
]

def main() -> int:
    eng = get_engine()
    if eng is None:
        print(json.dumps({
            "ok": False,
            "reason": "POSTGRES_DSN not configured",
        }))
        return 2
    try:
        insp = inspect(eng)
        existing = insp.get_table_names(schema="public")
        missing = [t for t in EXPECTED_TABLES if t not in existing]
        print(json.dumps({
            "ok": True,
            "existing": existing,
            "missing": missing,
        }))
        return 0
    except Exception as exc:  # pylint: disable=broad-except
        print(json.dumps({
            "ok": False,
            "reason": str(exc),
        }))
        return 1

if __name__ == "__main__":
    sys.exit(main())
