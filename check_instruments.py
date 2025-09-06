#!/usr/bin/env python3
"""Check what's in the instruments table and populate if needed."""

import sys
import os
sys.path.append('backend')

from backend.utils.postgres import get_conn
from sqlalchemy import text

def check_instruments():
    """Check what's in the instruments table."""
    try:
        with get_conn() as conn:
            if conn is None:
                print("No database connection")
                return
            
            # Check if table exists and has data
            result = conn.execute(text("SELECT COUNT(*) FROM instruments"))
            count = result.scalar()
            print(f"Instruments table has {count} rows")
            
            if count > 0:
                # Check column names first
                result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'instruments' ORDER BY ordinal_position"))
                columns = [row[0] for row in result.fetchall()]
                print(f"Available columns: {columns}")
                
                # Show sample data
                result = conn.execute(text("SELECT token, short_name, company_name FROM instruments LIMIT 5"))
                rows = result.fetchall()
                print("Sample instruments:")
                for row in rows:
                    print(f"  {row[0]} - {row[1]} - {row[2]}")
            else:
                print("No instruments found. You may need to populate the instruments table first.")
                print("Run: python backend/create_instruments_table.py")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_instruments()
