#!/usr/bin/env python3
"""Check websocket_enabled status in instruments table."""

import sys
sys.path.append('backend')

from backend.utils.postgres import get_conn
from sqlalchemy import text

def check_websocket_status():
    with get_conn() as conn:
        # Check websocket_enabled count
        result = conn.execute(text("SELECT COUNT(*) FROM instruments WHERE websocket_enabled = true"))
        enabled_count = result.scalar()
        print(f"WebSocket enabled: {enabled_count}")
        
        # Check total count
        result = conn.execute(text("SELECT COUNT(*) FROM instruments"))
        total_count = result.scalar()
        print(f"Total instruments: {total_count}")
        
        # Check sample websocket_enabled values
        result = conn.execute(text("SELECT token, short_name, websocket_enabled FROM instruments LIMIT 5"))
        rows = result.fetchall()
        print("Sample data:")
        for row in rows:
            print(f"  {row[0]} - {row[1]} - {row[2]}")

if __name__ == "__main__":
    check_websocket_status()
