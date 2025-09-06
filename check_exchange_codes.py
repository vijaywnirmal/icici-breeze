#!/usr/bin/env python3
"""Check exchange codes in instruments table."""

import sys
sys.path.append('backend')

from backend.utils.postgres import get_conn
from sqlalchemy import text

def check_exchange_codes():
    with get_conn() as conn:
        # Get distinct exchange codes
        result = conn.execute(text("SELECT DISTINCT exchange_code FROM instruments"))
        exchange_codes = [row[0] for row in result.fetchall()]
        print("Exchange codes:", exchange_codes)
        
        # Get sample data with exchange codes
        result = conn.execute(text("SELECT token, short_name, exchange_code FROM instruments LIMIT 10"))
        rows = result.fetchall()
        print("\nSample data:")
        for row in rows:
            print(f"  {row[0]} - {row[1]} - {row[2]}")

if __name__ == "__main__":
    check_exchange_codes()
