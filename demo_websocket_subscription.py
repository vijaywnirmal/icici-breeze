#!/usr/bin/env python3
"""
Demonstration script showing how to enable WebSocket feeds for all tokens.
This shows the exact pattern you requested: breeze.subscribe_feeds(stock_token=[...])
"""

import sys
import os
sys.path.append('backend')

from backend.services.bulk_websocket_service import BULK_WS_SERVICE

def demo_websocket_subscription():
    """Demonstrate WebSocket subscription for all tokens."""
    
    print("WebSocket Subscription Demo")
    print("=" * 50)
    
    # Step 1: Get all tokens from database
    print("\n1. Fetching tokens from instruments table...")
    instruments = BULK_WS_SERVICE.get_all_tokens(limit=10)  # Get first 10 for demo
    print(f"✓ Found {len(instruments)} instruments")
    
    if not instruments:
        print("❌ No instruments found. Please check your database.")
        return
    
    # Show sample instruments
    print("\nSample instruments:")
    for i, inst in enumerate(instruments[:5]):
        print(f"  {i+1}. {inst['token']} - {inst['short_name']} ({inst['company_name']})")
    
    # Step 2: Format tokens for subscription
    print("\n2. Formatting tokens for WebSocket subscription...")
    formatted_tokens = BULK_WS_SERVICE.format_tokens_for_subscription(instruments)
    print(f"✓ Formatted {len(formatted_tokens)} tokens")
    
    # Show sample formatted tokens
    print("\nSample formatted tokens (4.1!TOKEN format):")
    for i, token in enumerate(formatted_tokens[:5]):
        print(f"  {i+1}. {token}")
    
    # Step 3: Show the exact code pattern you requested
    print("\n3. WebSocket Subscription Code Pattern:")
    print("=" * 40)
    print("Here's the exact code pattern you requested:")
    print()
    print("```python")
    print("# Get all tokens from database")
    print("instruments = BULK_WS_SERVICE.get_all_tokens()")
    print("formatted_tokens = BULK_WS_SERVICE.format_tokens_for_subscription(instruments)")
    print()
    print("# Connect to Breeze WebSocket")
    print("breeze = get_breeze()  # Your active Breeze session")
    print("breeze.client.ws_connect()")
    print()
    print("# Subscribe to all tokens using the exact pattern you requested:")
    print("breeze.client.subscribe_feeds(stock_token=formatted_tokens)")
    print("```")
    print()
    
    # Step 4: Show the actual tokens that would be subscribed
    print("4. Actual tokens that would be subscribed:")
    print("=" * 45)
    print("breeze.client.subscribe_feeds(stock_token=[")
    for i, token in enumerate(formatted_tokens[:10]):  # Show first 10
        comma = "," if i < len(formatted_tokens) - 1 else ""
        print(f"    '{token}'{comma}")
    if len(formatted_tokens) > 10:
        print(f"    # ... and {len(formatted_tokens) - 10} more tokens")
    print("])")
    
    # Step 5: Show API usage
    print("\n5. API Endpoints Available:")
    print("=" * 30)
    print("• GET  /api/bulk-websocket/tokens?limit=N     - Get available tokens")
    print("• POST /api/bulk-websocket/subscribe-sample   - Subscribe to sample tokens")
    print("• POST /api/bulk-websocket/subscribe-all      - Subscribe to all tokens")
    print("• GET  /api/bulk-websocket/status             - Get subscription status")
    print("• POST /api/bulk-websocket/unsubscribe-all    - Unsubscribe from all")
    
    # Step 6: Show WebSocket connection info
    print("\n6. WebSocket Connection:")
    print("=" * 25)
    print("WebSocket URL: ws://localhost:8000/ws/ticks")
    print("Message format for subscription:")
    print("""
{
    "action": "subscribe_many",
    "symbols": [
        {
            "stock_code": "NIFTY",
            "token": "4.1!3499",
            "exchange_code": "NSE",
            "product_type": "cash"
        },
        {
            "stock_code": "BANKNIFTY", 
            "token": "4.1!2885",
            "exchange_code": "NSE",
            "product_type": "cash"
        }
    ]
}
    """)
    
    print("\n" + "=" * 50)
    print("✅ Demo completed!")
    print("💡 To actually enable WebSocket feeds, you need:")
    print("   1. An active Breeze session (login first)")
    print("   2. Call the API endpoints or use the service directly")
    print("   3. Connect to ws://localhost:8000/ws/ticks for real-time data")

def show_token_examples():
    """Show examples of token formatting."""
    print("\nToken Formatting Examples:")
    print("=" * 30)
    
    examples = [
        ("10", "NSE", "4.1!10"),
        ("100", "NSE", "4.1!100"),
        ("10056", "NSE", "4.1!10056"),
        ("2885", "NSE", "4.1!2885"),
        ("3499", "NSE", "4.1!3499"),
    ]
    
    for token, exchange, formatted in examples:
        print(f"  {token} ({exchange}) → {formatted}")

if __name__ == "__main__":
    demo_websocket_subscription()
    show_token_examples()
