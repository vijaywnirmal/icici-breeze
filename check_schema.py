#!/usr/bin/env python3
"""Check database schema for instruments table."""

import sys
sys.path.append('backend')

from backend.utils.postgres import get_conn
from sqlalchemy import text

def check_schema():
    with get_conn() as conn:
        # Get column names
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'instruments' ORDER BY ordinal_position"))
        columns = [row[0] for row in result.fetchall()]
        print("Columns:", columns)
        
        # Get sample data
        result = conn.execute(text("SELECT * FROM instruments LIMIT 1"))
        row = result.fetchone()
        print("Sample row:", row)
        
        # Check if is_active column exists
        if 'is_active' in columns:
            print("✓ is_active column exists")
        else:
            print("✗ is_active column does not exist")
            
        # Check for websocket_enabled column
        if 'websocket_enabled' in columns:
            print("✓ websocket_enabled column exists")
        else:
            print("✗ websocket_enabled column does not exist")

if __name__ == "__main__":
    check_schema()
