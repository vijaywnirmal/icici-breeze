#!/usr/bin/env python3
"""
Test script for bulk WebSocket subscription functionality.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_bulk_websocket():
    """Test bulk WebSocket subscription functionality."""
    
    print("Testing Bulk WebSocket Subscription Service")
    print("=" * 50)
    
    # Test 1: Get available tokens
    print("\n1. Getting available tokens...")
    try:
        response = requests.get(f"{BASE_URL}/api/bulk-websocket/tokens?limit=10")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Found {data['count']} tokens")
            print("Sample tokens:")
            for token in data['tokens'][:5]:
                print(f"  - {token['token']} ({token['short_name']})")
        else:
            print(f"✗ Failed to get tokens: {response.status_code}")
            return
    except Exception as e:
        print(f"✗ Error getting tokens: {e}")
        return
    
    # Test 2: Get subscription status
    print("\n2. Getting subscription status...")
    try:
        response = requests.get(f"{BASE_URL}/api/bulk-websocket/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Connected: {data['connected']}")
            print(f"✓ Subscribed count: {data['subscribed_count']}")
        else:
            print(f"✗ Failed to get status: {response.status_code}")
    except Exception as e:
        print(f"✗ Error getting status: {e}")
    
    # Test 3: Subscribe to sample tokens
    print("\n3. Subscribing to sample tokens...")
    try:
        response = requests.post(f"{BASE_URL}/api/bulk-websocket/subscribe-sample?sample_size=5")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ {data['message']}")
            print(f"✓ Subscribed: {data['subscribed_count']}/{data['total_tokens']}")
            if data['failed_count'] > 0:
                print(f"⚠ Failed: {data['failed_count']} tokens")
        else:
            print(f"✗ Failed to subscribe: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Error subscribing: {e}")
    
    # Test 4: Check status after subscription
    print("\n4. Checking status after subscription...")
    try:
        response = requests.get(f"{BASE_URL}/api/bulk-websocket/status")
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Connected: {data['connected']}")
            print(f"✓ Subscribed count: {data['subscribed_count']}")
            if data['subscribed_tokens']:
                print("Sample subscribed tokens:")
                for token in data['subscribed_tokens'][:3]:
                    print(f"  - {token}")
        else:
            print(f"✗ Failed to get status: {response.status_code}")
    except Exception as e:
        print(f"✗ Error getting status: {e}")
    
    # Test 5: Test WebSocket connection (if market is open)
    print("\n5. Testing WebSocket connection...")
    try:
        import websocket
        import threading
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get('type') == 'tick':
                    print(f"✓ Received tick: {data.get('symbol')} - LTP: {data.get('ltp')}")
            except Exception as e:
                print(f"Error parsing message: {e}")
        
        def on_error(ws, error):
            print(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print("WebSocket closed")
        
        def on_open(ws):
            print("✓ WebSocket connected")
            # Subscribe to a few tokens
            subscribe_msg = {
                "action": "subscribe_many",
                "symbols": [
                    {"stock_code": "NIFTY", "token": "4.1!3499", "exchange_code": "NSE", "product_type": "cash"},
                    {"stock_code": "BANKNIFTY", "token": "4.1!2885", "exchange_code": "NSE", "product_type": "cash"}
                ]
            }
            ws.send(json.dumps(subscribe_msg))
            print("✓ Sent subscription message")
        
        # Connect to WebSocket
        ws_url = "ws://localhost:8000/ws/ticks"
        ws = websocket.WebSocketApp(ws_url, on_message=on_message, on_error=on_error, on_close=on_close, on_open=on_open)
        
        # Run for 10 seconds
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        print("✓ WebSocket test started (running for 10 seconds)...")
        time.sleep(10)
        
        ws.close()
        print("✓ WebSocket test completed")
        
    except ImportError:
        print("⚠ websocket-client not installed, skipping WebSocket test")
        print("  Install with: pip install websocket-client")
    except Exception as e:
        print(f"✗ WebSocket test error: {e}")
    
    print("\n" + "=" * 50)
    print("Bulk WebSocket test completed!")

if __name__ == "__main__":
    test_bulk_websocket()
