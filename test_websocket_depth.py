#!/usr/bin/env python3
"""
Test script to verify websocket market depth data format
"""

import asyncio
import json
import websockets
from backend.utils.config import settings

async def test_websocket_depth():
    """Test websocket market depth data reception"""
    print("🧪 Testing WebSocket Market Depth Data")
    print("=" * 50)
    
    # WebSocket URL
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
            
            print("⏳ Listening for market depth data for 20 seconds...")
            
            depth_updates = []
            start_time = asyncio.get_event_loop().time()
            
            while asyncio.get_event_loop().time() - start_time < 20:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    
                    if data.get("type") == "tick":
                        symbol = data.get("symbol", "Unknown")
                        ltp = data.get("ltp", "N/A")
                        bids = data.get("bids")
                        asks = data.get("asks")
                        
                        print(f"\n📊 Tick: {symbol} | LTP: {ltp}")
                        
                        if bids or asks:
                            print(f"   📈 Market Depth Found!")
                            print(f"   Bids: {len(bids) if bids else 0} levels")
                            print(f"   Asks: {len(asks) if asks else 0} levels")
                            
                            if bids:
                                print(f"   Top Bid: ₹{bids[0].get('price', 'N/A')} x {bids[0].get('qty', 'N/A')}")
                            if asks:
                                print(f"   Top Ask: ₹{asks[0].get('price', 'N/A')} x {asks[0].get('qty', 'N/A')}")
                            
                            depth_updates.append({
                                'symbol': symbol,
                                'bids': bids,
                                'asks': asks,
                                'timestamp': data.get('timestamp')
                            })
                        else:
                            print(f"   ⚠️  No market depth data")
                            
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
                    break
            
            print(f"\n📊 WebSocket Test Results:")
            print(f"   Total depth updates: {len(depth_updates)}")
            
            if depth_updates:
                print("✅ Market depth data received via WebSocket!")
                print("\n📋 Sample data structure:")
                sample = depth_updates[0]
                print(f"   Symbol: {sample['symbol']}")
                print(f"   Bids structure: {sample['bids'][0] if sample['bids'] else 'None'}")
                print(f"   Asks structure: {sample['asks'][0] if sample['asks'] else 'None'}")
            else:
                print("⚠️  No market depth data received via WebSocket")
            
            return len(depth_updates) > 0
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_websocket_depth())
    if success:
        print("\n🎉 WebSocket market depth test completed successfully!")
    else:
        print("\n⚠️  WebSocket market depth test completed with issues")
