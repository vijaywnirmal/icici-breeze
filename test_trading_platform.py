#!/usr/bin/env python3
"""
Test script for the Trading Platform functionality.
This script tests the search API and WebSocket subscription.
"""

import asyncio
import json
import requests
import websockets
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"

def test_search_api():
    """Test the stock search API endpoint."""
    print("🔍 Testing Stock Search API...")
    
    try:
        # Test search for popular stocks
        test_queries = ["RELIANCE", "TCS", "HDFC", "INFY", "WIPRO"]
        
        for query in test_queries:
            print(f"\n  Searching for: {query}")
            response = requests.get(f"{API_BASE}/api/instruments/live-trading", params={"q": query, "limit": 5})
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    items = data.get("items", [])
                    print(f"    ✅ Found {len(items)} results")
                    for item in items[:3]:  # Show first 3 results
                        print(f"      - {item.get('symbol')}: {item.get('company_name')}")
                else:
                    print(f"    ❌ API Error: {data.get('error', 'Unknown error')}")
            else:
                print(f"    ❌ HTTP Error: {response.status_code}")
                
    except Exception as e:
        print(f"    ❌ Exception: {e}")

def test_market_status():
    """Test the market status API."""
    print("\n📊 Testing Market Status API...")
    
    try:
        response = requests.get(f"{API_BASE}/api/market/status")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                is_open = data.get("is_open", False)
                status = "🟢 OPEN" if is_open else "🔴 CLOSED"
                print(f"    ✅ Market Status: {status}")
                return is_open
            else:
                print(f"    ❌ API Error: {data.get('error', 'Unknown error')}")
        else:
            print(f"    ❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"    ❌ Exception: {e}")
    
    return False

async def test_websocket_connection():
    """Test WebSocket connection and subscription."""
    print("\n🔌 Testing WebSocket Connection...")
    
    try:
        # Connect to WebSocket
        uri = f"{WS_BASE}/ws/ticks"
        print(f"    Connecting to: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("    ✅ WebSocket connected successfully")
            
            # Test subscription to a sample stock
            test_symbol = "RELIANCE"
            subscription_message = {
                "action": "subscribe",
                "symbol": test_symbol,
                "exchange_code": "NSE",
                "product_type": "cash"
            }
            
            print(f"    📡 Subscribing to {test_symbol}...")
            await websocket.send(json.dumps(subscription_message))
            
            # Wait for messages for a few seconds
            print("    ⏳ Waiting for live data (5 seconds)...")
            timeout = 5
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "tick":
                        print(f"    📈 Live Data Received:")
                        print(f"      Symbol: {data.get('symbol')}")
                        print(f"      LTP: ₹{data.get('ltp', 'N/A')}")
                        print(f"      Change: {data.get('change_pct', 'N/A')}%")
                        print(f"      Bid: ₹{data.get('bid', 'N/A')}")
                        print(f"      Ask: ₹{data.get('ask', 'N/A')}")
                        break
                    else:
                        print(f"    📨 Message: {data}")
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"    ❌ Error receiving message: {e}")
                    break
            
            print("    ✅ WebSocket test completed")
            
    except Exception as e:
        print(f"    ❌ WebSocket Error: {e}")

def test_bulk_websocket_api():
    """Test the bulk WebSocket API endpoints."""
    print("\n📡 Testing Bulk WebSocket API...")
    
    try:
        # Test getting all tokens
        print("    Getting all available tokens...")
        response = requests.get(f"{API_BASE}/api/bulk-websocket/tokens")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                count = data.get("count", 0)
                print(f"    ✅ Found {count} WebSocket-enabled tokens")
                
                if count > 0:
                    # Test subscription status
                    print("    Checking subscription status...")
                    status_response = requests.get(f"{API_BASE}/api/bulk-websocket/status")
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        if status_data.get("success"):
                            print(f"    ✅ Subscription Status: {status_data.get('status', 'Unknown')}")
                        else:
                            print(f"    ❌ Status API Error: {status_data.get('error')}")
                    else:
                        print(f"    ❌ Status HTTP Error: {status_response.status_code}")
            else:
                print(f"    ❌ Tokens API Error: {data.get('error', 'Unknown error')}")
        else:
            print(f"    ❌ Tokens HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"    ❌ Exception: {e}")

async def main():
    """Run all tests."""
    print("🚀 Starting Trading Platform Tests")
    print("=" * 50)
    
    # Test API endpoints
    test_search_api()
    market_open = test_market_status()
    test_bulk_websocket_api()
    
    # Test WebSocket if market is open
    if market_open:
        await test_websocket_connection()
    else:
        print("\n⚠️  Market is closed - skipping WebSocket live data test")
    
    print("\n" + "=" * 50)
    print("✅ Trading Platform Tests Completed!")
    print("\n📱 To use the trading platform:")
    print("   1. Start the backend server: cd backend && python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload")
    print("   2. Start the frontend: cd frontend && npm run dev")
    print("   3. Login at: http://localhost:5173/")
    print("   4. Navigate to: http://localhost:5173/live-trading")
    print("   5. Search for stocks and add them to your watchlist!")

if __name__ == "__main__":
    asyncio.run(main())
