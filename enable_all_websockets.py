#!/usr/bin/env python3
"""
Script to enable WebSocket feeds for all tokens using breeze.subscribe_feeds(stock_token=[...])
This demonstrates the exact pattern you requested.
"""

import sys
import os
sys.path.append('backend')

from backend.services.bulk_websocket_service import BULK_WS_SERVICE
from backend.utils.session import get_breeze

def enable_all_websockets():
    """Enable WebSocket feeds for all tokens from instruments table."""
    
    print("Enabling WebSocket feeds for all tokens...")
    print("=" * 50)
    
    # Get Breeze service
    breeze = get_breeze()
    if not breeze:
        print("❌ No Breeze session found.")
        print("   Please login first through the web interface.")
        return
    
    # Get all tokens from database
    print("📊 Fetching tokens from instruments table...")
    instruments = BULK_WS_SERVICE.get_all_tokens()
    print(f"✓ Found {len(instruments)} active instruments")
    
    if not instruments:
        print("❌ No instruments found in database")
        return
    
    # Format tokens for subscription (4.1!TOKEN format)
    print("🔧 Formatting tokens for subscription...")
    formatted_tokens = BULK_WS_SERVICE.format_tokens_for_subscription(instruments)
    print(f"✓ Formatted {len(formatted_tokens)} tokens")
    
    # Show sample of formatted tokens
    print("\nSample formatted tokens:")
    for i, token in enumerate(formatted_tokens[:10]):
        print(f"  {i+1}. {token}")
    if len(formatted_tokens) > 10:
        print(f"  ... and {len(formatted_tokens) - 10} more")
    
    # Connect to WebSocket
    print("\n🔌 Connecting to Breeze WebSocket...")
    try:
        BULK_WS_SERVICE.connect()
        print("✓ WebSocket connected")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    # Subscribe to all tokens using breeze.subscribe_feeds(stock_token=[...])
    print(f"\n📡 Subscribing to {len(formatted_tokens)} tokens...")
    print("Using: breeze.subscribe_feeds(stock_token=[...])")
    
    try:
        # This is the exact pattern you requested
        breeze.client.subscribe_feeds(stock_token=formatted_tokens)
        print(f"✓ Successfully subscribed to {len(formatted_tokens)} tokens!")
        
        # Store subscribed tokens
        BULK_WS_SERVICE._subscribed_tokens = formatted_tokens
        
        print("\n🎉 WebSocket feeds enabled for all tokens!")
        print(f"📊 Total tokens subscribed: {len(formatted_tokens)}")
        
        # Show subscription status
        status = BULK_WS_SERVICE.get_subscription_status()
        print(f"🔗 Connected: {status['connected']}")
        print(f"📡 Subscribed: {status['subscribed_count']}")
        
    except Exception as e:
        print(f"❌ Failed to subscribe: {e}")
        return
    
    print("\n" + "=" * 50)
    print("✅ All WebSocket feeds are now active!")
    print("💡 You can now receive real-time data for all instruments")
    print("🔍 Check the WebSocket endpoint at ws://localhost:8000/ws/ticks")

def test_sample_subscription():
    """Test with a small sample first."""
    
    print("Testing with sample tokens...")
    print("=" * 30)
    
    # Test with just 5 tokens
    result = BULK_WS_SERVICE.subscribe_sample_tokens(5)
    
    if result["success"]:
        print(f"✅ {result['message']}")
        print(f"📊 Subscribed: {result['subscribed_count']}/{result['total_tokens']}")
    else:
        print(f"❌ {result['message']}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enable WebSocket feeds for all tokens")
    parser.add_argument("--test", action="store_true", help="Test with sample tokens only")
    parser.add_argument("--all", action="store_true", help="Subscribe to all tokens")
    
    args = parser.parse_args()
    
    if args.test:
        test_sample_subscription()
    elif args.all:
        enable_all_websockets()
    else:
        print("Choose an option:")
        print("  --test    : Test with sample tokens")
        print("  --all     : Subscribe to all tokens")
        print("\nExample:")
        print("  python enable_all_websockets.py --test")
        print("  python enable_all_websockets.py --all")
