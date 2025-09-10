#!/usr/bin/env python3
"""
Test script to verify market depth functionality with Breeze API
"""

import json
import time
from backend.services.breeze_service import BreezeService
from backend.utils.session import get_breeze

def test_market_depth():
    """Test market depth subscription and data reception"""
    print("🧪 Testing Market Depth Functionality")
    print("=" * 50)
    
    try:
        # Get Breeze service
        breeze = get_breeze()
        if not breeze:
            print("❌ No Breeze session found. Please login first.")
            return False
            
        print("✅ Breeze session found")
        
        # Test subscription with market depth enabled
        print("\n📡 Subscribing to NIFTY option with market depth...")
        
        # Subscribe to a NIFTY option with market depth
        response = breeze.client.subscribe_feeds(
            exchange_code="NFO",
            stock_code="NIFTY",
            expiry_date="13-Feb-2025",
            strike_price="23550",
            right="call",
            product_type="options",
            get_market_depth=True,
            get_exchange_quotes=True
        )
        
        print(f"📋 Subscription response: {response}")
        
        if "successfully" in str(response).lower():
            print("✅ Subscription successful")
            
            # Set up tick handler to capture market depth data
            market_depth_data = []
            
            def on_ticks(ticks):
                print(f"\n📊 Tick received: {ticks.get('symbol', 'Unknown')}")
                print(f"   Time: {ticks.get('time', 'N/A')}")
                print(f"   LTP: {ticks.get('last', 'N/A')}")
                print(f"   Close: {ticks.get('close', 'N/A')}")
                
                # Check for market depth data
                depth = ticks.get('depth')
                if depth:
                    print(f"   📈 Market Depth Data Found!")
                    print(f"   Depth levels: {len(depth)}")
                    
                    # Show first few levels
                    for i, level in enumerate(depth[:3]):
                        print(f"   Level {i+1}: {level}")
                    
                    market_depth_data.append({
                        'timestamp': ticks.get('time'),
                        'symbol': ticks.get('symbol'),
                        'depth': depth
                    })
                else:
                    print(f"   ⚠️  No market depth data in this tick")
                
                # Check for other market data
                if ticks.get('quotes') == 'Market Depth':
                    print(f"   🎯 This is a market depth tick!")
                
            # Set the tick handler
            breeze.client.on_ticks = on_ticks
            
            print("\n⏳ Listening for market depth data for 30 seconds...")
            print("   (Make sure the market is open for live data)")
            
            # Listen for 30 seconds
            start_time = time.time()
            while time.time() - start_time < 30:
                time.sleep(1)
                if len(market_depth_data) >= 3:  # Stop after getting 3 depth updates
                    break
            
            print(f"\n📊 Market Depth Test Results:")
            print(f"   Total depth updates received: {len(market_depth_data)}")
            
            if market_depth_data:
                print("✅ Market depth data is being received!")
                print("\n📋 Sample depth data structure:")
                sample = market_depth_data[0]
                print(f"   Symbol: {sample['symbol']}")
                print(f"   Timestamp: {sample['timestamp']}")
                print(f"   Depth levels: {len(sample['depth'])}")
                
                # Show the structure of depth data
                if sample['depth']:
                    print(f"   First level keys: {list(sample['depth'][0].keys())}")
            else:
                print("⚠️  No market depth data received")
                print("   This could be because:")
                print("   - Market is closed")
                print("   - No trading activity for this option")
                print("   - Market depth data is not available for this instrument")
            
            # Unsubscribe
            print("\n🔄 Unsubscribing...")
            try:
                breeze.client.unsubscribe_feeds(
                    exchange_code="NFO",
                    stock_code="NIFTY",
                    expiry_date="13-Feb-2025",
                    strike_price="23550",
                    right="call",
                    product_type="options"
                )
                print("✅ Unsubscribed successfully")
            except Exception as e:
                print(f"⚠️  Error unsubscribing: {e}")
            
            return len(market_depth_data) > 0
            
        else:
            print(f"❌ Subscription failed: {response}")
            return False
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

if __name__ == "__main__":
    success = test_market_depth()
    if success:
        print("\n🎉 Market depth test completed successfully!")
    else:
        print("\n⚠️  Market depth test completed with issues")
