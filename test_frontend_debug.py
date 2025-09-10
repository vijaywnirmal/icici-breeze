#!/usr/bin/env python3
"""
Simple test to debug frontend websocket connection and market depth data
"""

import asyncio
import json
import websockets

async def test_frontend_debug():
    """Test websocket connection and log all messages"""
    print("🧪 Testing Frontend WebSocket Debug")
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
            
            print("⏳ Listening for ALL messages for 30 seconds...")
            print("   (This will show all data being sent to frontend)")
            
            message_count = 0
            depth_messages = 0
            
            while message_count < 50:  # Limit to 50 messages for testing
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    message_count += 1
                    
                    print(f"\n📨 Message #{message_count}:")
                    print(f"   Type: {data.get('type', 'unknown')}")
                    print(f"   Symbol: {data.get('symbol', 'N/A')}")
                    
                    if data.get('type') == 'tick':
                        print(f"   LTP: {data.get('ltp', 'N/A')}")
                        print(f"   Close: {data.get('close', 'N/A')}")
                        print(f"   Bids: {len(data.get('bids', []))} levels")
                        print(f"   Asks: {len(data.get('asks', []))} levels")
                        
                        if data.get('bids') or data.get('asks'):
                            depth_messages += 1
                            print(f"   📊 MARKET DEPTH FOUND!")
                            if data.get('bids'):
                                print(f"      Bids: {data['bids'][:2]}")
                            if data.get('asks'):
                                print(f"      Asks: {data['asks'][:2]}")
                    
                    elif data.get('type') == 'subscribed':
                        print(f"   ✅ Subscription confirmed: {data.get('message', 'N/A')}")
                    
                    elif data.get('type') == 'error':
                        print(f"   ❌ Error: {data.get('message', 'N/A')}")
                    
                    # Show full message for first few ticks
                    if message_count <= 3:
                        print(f"   Full data: {json.dumps(data, indent=2)}")
                        
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
                print("✅ Market depth data is being sent to frontend!")
            else:
                print("⚠️  No market depth data received")
                print("   This could be because:")
                print("   - Market is closed")
                print("   - No trading activity for these options")
                print("   - Market depth data is not available")
            
            return depth_messages > 0
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_frontend_debug())
    if success:
        print("\n🎉 Frontend debug test completed successfully!")
    else:
        print("\n⚠️  Frontend debug test completed with issues")
