#!/usr/bin/env python3
"""
Test script to verify market depth data flow from backend to frontend
"""

import asyncio
import json
import websockets

async def test_depth_data_flow():
    """Test the complete data flow for market depth"""
    print("🧪 Testing Market Depth Data Flow")
    print("=" * 50)
    
    ws_url = "ws://localhost:8000/ws/options"
    
    try:
        print(f"🔌 Connecting to {ws_url}")
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connected")
            
            # Subscribe to NIFTY options
            subscribe_msg = {
                "action": "subscribe_options",
                "underlying": "NIFTY",
                "expiry_date": "13-Feb-2025",
                "strikes": [23550, 23600, 23650],
                "right": "both"
            }
            
            print(f"📡 Sending subscription: {json.dumps(subscribe_msg, indent=2)}")
            await websocket.send(json.dumps(subscribe_msg))
            
            print("⏳ Listening for market depth data...")
            
            message_count = 0
            depth_messages = 0
            
            while message_count < 20:  # Limit to 20 messages
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    message_count += 1
                    
                    print(f"\n📨 Message #{message_count}:")
                    print(f"   Type: {data.get('type', 'unknown')}")
                    print(f"   Symbol: {data.get('symbol', 'N/A')}")
                    
                    if data.get('type') == 'tick':
                        print(f"   LTP: {data.get('ltp', 'N/A')}")
                        print(f"   Strike: {data.get('strike_price', 'N/A')}")
                        print(f"   Right: {data.get('right_type', 'N/A')}")
                        
                        # Check for market depth data
                        bids = data.get('bids', [])
                        asks = data.get('asks', [])
                        
                        print(f"   Bids: {len(bids)} levels")
                        print(f"   Asks: {len(asks)} levels")
                        
                        if bids or asks:
                            depth_messages += 1
                            print(f"   📊 MARKET DEPTH FOUND!")
                            
                            if bids:
                                print(f"      Bids structure:")
                                for i, bid in enumerate(bids[:3]):  # Show first 3
                                    print(f"        Level {i+1}: {bid}")
                            
                            if asks:
                                print(f"      Asks structure:")
                                for i, ask in enumerate(asks[:3]):  # Show first 3
                                    print(f"        Level {i+1}: {ask}")
                            
                            # Check if data structure matches frontend expectations
                            if bids and len(bids) > 0:
                                first_bid = bids[0]
                                has_price = 'price' in first_bid
                                has_qty = 'qty' in first_bid
                                print(f"      ✅ Bid structure check: price={has_price}, qty={qty}")
                            
                            if asks and len(asks) > 0:
                                first_ask = asks[0]
                                has_price = 'price' in first_ask
                                has_qty = 'qty' in first_ask
                                print(f"      ✅ Ask structure check: price={has_price}, qty={qty}")
                        
                        # Show full message for first few ticks
                        if message_count <= 2:
                            print(f"   Full data: {json.dumps(data, indent=2)}")
                    
                    elif data.get('type') == 'subscribed':
                        print(f"   ✅ Subscription confirmed: {data.get('message', 'N/A')}")
                    
                except asyncio.TimeoutError:
                    print("⏰ Timeout waiting for message")
                    break
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
                    break
            
            print(f"\n📊 Test Results:")
            print(f"   Total messages received: {message_count}")
            print(f"   Messages with market depth: {depth_messages}")
            
            if depth_messages > 0:
                print("✅ Market depth data is flowing correctly!")
                print("   The issue might be in frontend processing or display logic.")
            else:
                print("⚠️  No market depth data received")
                print("   This could be because market is closed or no trading activity.")
            
            return depth_messages > 0
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_depth_data_flow())
    if success:
        print("\n🎉 Market depth data flow test completed successfully!")
    else:
        print("\n⚠️  Market depth data flow test completed with issues")
