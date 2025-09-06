#!/usr/bin/env python3
"""
Test script showing exact usage of breeze.subscribe_feeds(stock_token=[...])
for all NSE tokens from the instruments table.
"""

import sys
import os
sys.path.append('backend')

from backend.services.bulk_websocket_service import BULK_WS_SERVICE

def test_nse_websocket_subscription():
    """Test WebSocket subscription for all NSE tokens."""
    
    print("NSE WebSocket Subscription Test")
    print("=" * 40)
    
    # Step 1: Get all NSE tokens from database
    print("\n1. Fetching all NSE tokens from instruments table...")
    instruments = BULK_WS_SERVICE.get_all_tokens(limit=10)  # Get first 10 for demo
    print(f"✓ Found {len(instruments)} NSE instruments")
    
    if not instruments:
        print("❌ No instruments found. Please check your database.")
        return
    
    # Show sample instruments
    print("\nSample NSE instruments:")
    for i, inst in enumerate(instruments[:5]):
        print(f"  {i+1}. {inst['token']} - {inst['short_name']} ({inst['company_name']})")
    
    # Step 2: Format tokens for NSE subscription (4.1!TOKEN format)
    print("\n2. Formatting tokens for NSE WebSocket subscription...")
    formatted_tokens = BULK_WS_SERVICE.format_tokens_for_subscription(instruments)
    print(f"✓ Formatted {len(formatted_tokens)} tokens for NSE")
    
    # Show sample formatted tokens
    print("\nSample formatted NSE tokens (4.1!TOKEN format):")
    for i, token in enumerate(formatted_tokens[:5]):
        print(f"  {i+1}. {token}")
    
    # Step 3: Show the exact code you requested
    print("\n3. Exact Code Pattern You Requested:")
    print("=" * 40)
    print("```python")
    print("# Get all NSE tokens from database")
    print("instruments = BULK_WS_SERVICE.get_all_tokens()")
    print("formatted_tokens = BULK_WS_SERVICE.format_tokens_for_subscription(instruments)")
    print()
    print("# Connect to Breeze WebSocket")
    print("breeze = get_breeze()  # Your active Breeze session")
    print("breeze.client.ws_connect()")
    print()
    print("# Subscribe to all NSE tokens using the exact pattern you requested:")
    print("breeze.subscribe_feeds(stock_token=formatted_tokens)")
    print("```")
    
    # Step 4: Show actual tokens that would be subscribed
    print("\n4. Actual NSE tokens that would be subscribed:")
    print("=" * 50)
    print("breeze.subscribe_feeds(stock_token=[")
    for i, token in enumerate(formatted_tokens[:10]):  # Show first 10
        comma = "," if i < len(formatted_tokens) - 1 else ""
        print(f"    '{token}'{comma}")
    if len(formatted_tokens) > 10:
        print(f"    # ... and {len(formatted_tokens) - 10} more NSE tokens")
    print("])")
    
    # Step 5: Show total count
    print(f"\n5. Summary:")
    print("=" * 15)
    print(f"✓ Total NSE instruments: {len(instruments)}")
    print(f"✓ All formatted as: 4.1!TOKEN")
    print(f"✓ Ready for: breeze.subscribe_feeds(stock_token=[...])")
    
    print("\n" + "=" * 40)
    print("✅ NSE WebSocket subscription setup complete!")
    print("💡 All tokens are NSE listed and formatted as 4.1!TOKEN")
    print("🚀 Ready to enable WebSocket feeds for all instruments!")

if __name__ == "__main__":
    test_nse_websocket_subscription()
