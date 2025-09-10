#!/usr/bin/env python3
"""
Direct test of Breeze API to check market depth data availability
"""

import json
import time
from backend.services.breeze_service import BreezeService
from backend.utils.session import get_breeze

def test_breeze_direct():
    """Test Breeze API directly for market depth data"""
    print("🧪 Testing Breeze API Direct Market Depth")
    print("=" * 50)
    
    try:
        # Get Breeze service
        breeze = get_breeze()
        if not breeze:
            print("❌ No Breeze session found. Please login first.")
            return False
            
        print("✅ Breeze session found")
        
        # Test market status first
        print("\n📊 Checking market status...")
        try:
            market_status = breeze.client.get_market_status()
            print(f"Market status: {market_status}")
        except Exception as e:
            print(f"⚠️  Could not get market status: {e}")
        
        # Test with a simple equity first to see if market depth works
        print("\n📡 Testing market depth with NIFTY equity...")
        try:
            # Subscribe to NIFTY equity with market depth
            response = breeze.client.subscribe_feeds(
                exchange_code="NSE",
                stock_code="NIFTY",
                product_type="cash",
                get_market_depth=True,
                get_exchange_quotes=True
            )
            print(f"Equity subscription response: {response}")
            
            # Set up tick handler
            equity_ticks = []
            
            def on_ticks(ticks):
                print(f"\n📊 Equity Tick: {ticks.get('symbol', 'Unknown')}")
                print(f"   Time: {ticks.get('time', 'N/A')}")
                print(f"   LTP: {ticks.get('last', 'N/A')}")
                
                depth = ticks.get('depth')
                if depth:
                    print(f"   📈 Market Depth Data Found!")
                    print(f"   Depth levels: {len(depth)}")
                    print(f"   First level: {depth[0] if depth else 'None'}")
                    equity_ticks.append(ticks)
                else:
                    print(f"   ⚠️  No market depth data")
            
            breeze.client.on_ticks = on_ticks
            
            print("⏳ Listening for equity market depth for 10 seconds...")
            time.sleep(10)
            
            print(f"📊 Equity test results: {len(equity_ticks)} ticks with depth")
            
            # Unsubscribe
            try:
                breeze.client.unsubscribe_feeds(
                    exchange_code="NSE",
                    stock_code="NIFTY",
                    product_type="cash"
                )
                print("✅ Unsubscribed from equity")
            except Exception as e:
                print(f"⚠️  Error unsubscribing from equity: {e}")
            
        except Exception as e:
            print(f"❌ Equity test failed: {e}")
        
        # Now test with options
        print("\n📡 Testing market depth with NIFTY options...")
        try:
            # Subscribe to NIFTY option with market depth
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
            print(f"Option subscription response: {response}")
            
            # Set up tick handler
            option_ticks = []
            
            def on_ticks_option(ticks):
                print(f"\n📊 Option Tick: {ticks.get('symbol', 'Unknown')}")
                print(f"   Time: {ticks.get('time', 'N/A')}")
                print(f"   LTP: {ticks.get('last', 'N/A')}")
                print(f"   Strike: {ticks.get('strike_price', 'N/A')}")
                print(f"   Right: {ticks.get('right', 'N/A')}")
                
                depth = ticks.get('depth')
                if depth:
                    print(f"   📈 Market Depth Data Found!")
                    print(f"   Depth levels: {len(depth)}")
                    print(f"   First level: {depth[0] if depth else 'None'}")
                    option_ticks.append(ticks)
                else:
                    print(f"   ⚠️  No market depth data")
                    print(f"   Available keys: {list(ticks.keys())}")
            
            breeze.client.on_ticks = on_ticks_option
            
            print("⏳ Listening for option market depth for 15 seconds...")
            time.sleep(15)
            
            print(f"📊 Option test results: {len(option_ticks)} ticks with depth")
            
            # Unsubscribe
            try:
                breeze.client.unsubscribe_feeds(
                    exchange_code="NFO",
                    stock_code="NIFTY",
                    expiry_date="13-Feb-2025",
                    strike_price="23550",
                    right="call",
                    product_type="options"
                )
                print("✅ Unsubscribed from option")
            except Exception as e:
                print(f"⚠️  Error unsubscribing from option: {e}")
            
            return len(option_ticks) > 0
            
        except Exception as e:
            print(f"❌ Option test failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_breeze_direct()
    if success:
        print("\n🎉 Breeze direct test completed successfully!")
    else:
        print("\n⚠️  Breeze direct test completed with issues")
