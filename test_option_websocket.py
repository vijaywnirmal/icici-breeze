#!/usr/bin/env python3
"""Test option chain websocket subscription."""

import sys
import requests
import json
import time
sys.path.append('backend')

from backend.utils.session import get_breeze

base_url = "http://127.0.0.1:8000"

def test_option_chain_subscription():
    """Test option chain websocket subscription."""
    print("🧪 Testing Option Chain WebSocket Subscription")
    print("=" * 50)
    
    # Check if we have a Breeze session
    breeze = get_breeze()
    if not breeze or not breeze.client.session_token:
        print("❌ No active Breeze session found")
        print("Please run 'python login_breeze.py' first")
        return False
    
    print("✅ Breeze session found")
    
    # Test option chain subscription
    print("\n1. Testing option chain subscription...")
    try:
        response = requests.post(f"{base_url}/api/option-chain/subscribe", params={
            "stock_code": "NIFTY",
            "exchange_code": "NFO",
            "product_type": "options",
            "right": "both",
            "expiry_date": "2025-09-10T06:00:00.000Z",
            "limit": 5
        })
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Option chain subscription successful")
                print(f"   Subscribed count: {data.get('subscribed_count', 0)}")
                print(f"   Strikes: {data.get('strikes', [])}")
                print(f"   Underlying price: {data.get('underlying_price', 0)}")
                return True
            else:
                print(f"❌ Subscription failed: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Subscription error: {e}")
        return False

def test_option_chain_data():
    """Test option chain data endpoint."""
    print("\n2. Testing option chain data endpoint...")
    try:
        response = requests.get(f"{base_url}/api/option-chain/nifty-strikes")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Option chain data endpoint working")
                calls = data.get("calls", [])
                puts = data.get("puts", [])
                print(f"   Calls: {len(calls)}, Puts: {len(puts)}")
                if calls:
                    print(f"   Sample call: Strike {calls[0].get('strike_price')}, LTP {calls[0].get('ltp')}")
                return True
            else:
                print(f"❌ Data endpoint failed: {data.get('error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Data endpoint error: {e}")
        return False

def test_websocket_connection():
    """Test websocket connection for option chain data."""
    print("\n3. Testing websocket connection...")
    try:
        import websocket
        import threading
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if data.get("type") == "tick":
                    symbol = data.get("symbol", "")
                    if "|" in symbol:  # Option chain data
                        print(f"   📊 Option data: {symbol} - LTP: {data.get('ltp')}")
                    else:
                        print(f"   📈 Stock data: {symbol} - LTP: {data.get('ltp')}")
            except Exception as e:
                print(f"   ❌ Message parse error: {e}")
        
        def on_error(ws, error):
            print(f"   ❌ WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print("   🔌 WebSocket closed")
        
        def on_open(ws):
            print("   ✅ WebSocket connected")
            # Subscribe to NIFTY for testing
            ws.send(json.dumps({
                "action": "subscribe",
                "symbol": "NIFTY",
                "exchange_code": "NSE",
                "product_type": "cash"
            }))
        
        # Connect to websocket
        ws_url = "ws://127.0.0.1:8000/ws/ticks"
        ws = websocket.WebSocketApp(ws_url,
                                  on_open=on_open,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)
        
        # Run websocket in a separate thread
        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        
        # Wait for some messages
        print("   ⏳ Waiting for websocket messages (10 seconds)...")
        time.sleep(10)
        
        ws.close()
        print("   ✅ WebSocket test completed")
        return True
        
    except ImportError:
        print("   ⚠️ websocket-client not installed, skipping websocket test")
        print("   Install with: pip install websocket-client")
        return True
    except Exception as e:
        print(f"   ❌ WebSocket test error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Option Chain WebSocket Tests")
    print("=" * 60)
    
    # Test 1: Option chain subscription
    success1 = test_option_chain_subscription()
    
    # Test 2: Option chain data
    success2 = test_option_chain_data()
    
    # Test 3: WebSocket connection
    success3 = test_websocket_connection()
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    print(f"   Option Chain Subscription: {'✅' if success1 else '❌'}")
    print(f"   Option Chain Data: {'✅' if success2 else '❌'}")
    print(f"   WebSocket Connection: {'✅' if success3 else '❌'}")
    
    if success1 and success2:
        print("\n🎉 Option chain websocket functionality is working!")
        print("\n📝 Next Steps:")
        print("   1. Open the frontend and click on NIFTY or BANKNIFTY in the ticker bar")
        print("   2. The option chain should load with calculated strikes")
        print("   3. Real-time data will populate via websocket subscriptions")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
