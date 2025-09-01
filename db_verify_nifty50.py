from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import create_engine, text


def main() -> int:
    dsn: Optional[str] = os.getenv("POSTGRES_DSN")
    if not dsn:
        # Fallback to .env if available
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
            dsn = os.getenv("POSTGRES_DSN")
        except Exception:
            pass
    if not dsn:
        print("POSTGRES_DSN not set")
        return 1

    engine = create_engine(dsn)
    with engine.begin() as conn:
        rows = conn.execute(text(
            """
            SELECT symbol, stock_code, company_name
            FROM nifty50_list
            WHERE exchange = 'NSE'
            ORDER BY symbol
            """
        )).fetchall()
        total = len(rows)
        nulls = [r for r in rows if not (r[1] and str(r[1]).strip())]
        ada = [r for r in rows if str(r[0]).upper() == 'ADANIENT']
        print(f"total={total} null_stock_code={len(nulls)}")
        if ada:
            print(f"ADANIENT row: symbol={ada[0][0]} stock_code={ada[0][1]} company_name={ada[0][2]}")
        else:
            print("ADANIENT not found in nifty50_list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


