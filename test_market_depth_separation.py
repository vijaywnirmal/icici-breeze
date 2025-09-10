#!/usr/bin/env python3
"""
Test script to verify market depth separation implementation.
This script tests both exchange quotes and market depth subscriptions separately.
"""

import asyncio
import json
import websockets
import time
from datetime import datetime

async def test_market_depth_separation():
    """Test the separated market depth subscriptions."""
    
    # WebSocket URL
    ws_url = "ws://127.0.0.1:8000/ws/options"
    
    print("🧪 Testing Market Depth Separation Implementation")
    print("=" * 60)
    
    try:
        # Connect to WebSocket
        async with websockets.connect(ws_url) as websocket:
            print("✅ Connected to options WebSocket")
            
            # Test 1: Subscribe to exchange quotes only
            print("\n📊 Test 1: Subscribing to exchange quotes only...")
            quotes_subscription = {
                "action": "subscribe_options",
                "underlying": "NIFTY",
                "expiry_date": "13-Feb-2025",
                "strikes": [25000, 25100, 25200],
                "right": "both"
            }
            
            await websocket.send(json.dumps(quotes_subscription))
            print("✅ Exchange quotes subscription sent")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            quotes_response = json.loads(response)
            print(f"📥 Exchange quotes response: {quotes_response.get('type', 'unknown')}")
            
            # Test 2: Subscribe to market depth only
            print("\n📊 Test 2: Subscribing to market depth only...")
            depth_subscription = {
                "action": "subscribe_market_depth",
                "underlying": "NIFTY", 
                "expiry_date": "13-Feb-2025",
                "strikes": [25000, 25100],
                "right": "both"
            }
            
            await websocket.send(json.dumps(depth_subscription))
            print("✅ Market depth subscription sent")
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            depth_response = json.loads(response)
            print(f"📥 Market depth response: {depth_response.get('type', 'unknown')}")
            
            # Test 3: Listen for incoming data
            print("\n📊 Test 3: Listening for incoming data (10 seconds)...")
            start_time = time.time()
            message_count = 0
            
            while time.time() - start_time < 10:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    message = json.loads(response)
                    message_count += 1
                    
                    if message.get('type') == 'tick':
                        symbol = message.get('symbol', 'unknown')
                        has_depth = bool(message.get('bids') or message.get('asks') or message.get('depth'))
                        has_quotes = bool(message.get('ltp') or message.get('close'))
                        
                        print(f"📈 Tick {message_count}: {symbol} | Quotes: {has_quotes} | Depth: {has_depth}")
                        
                        if has_depth:
                            print(f"   📊 Market Depth Data: bids={len(message.get('bids', []))}, asks={len(message.get('asks', []))}")
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
                    break
            
            print(f"\n📊 Received {message_count} messages in 10 seconds")
            
            # Test 4: Unsubscribe
            print("\n📊 Test 4: Unsubscribing...")
            unsubscribe_msg = {"action": "unsubscribe_options"}
            await websocket.send(json.dumps(unsubscribe_msg))
            
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            unsubscribe_response = json.loads(response)
            print(f"📥 Unsubscribe response: {unsubscribe_response.get('type', 'unknown')}")
            
            print("\n✅ All tests completed successfully!")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

def main():
    """Run the test."""
    print("🚀 Starting Market Depth Separation Test")
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        result = asyncio.run(test_market_depth_separation())
        if result:
            print("\n🎉 Test PASSED - Market depth separation is working correctly!")
        else:
            print("\n💥 Test FAILED - Check the implementation")
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")

if __name__ == "__main__":
    main()
