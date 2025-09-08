#!/usr/bin/env python3
"""Test option chain functionality."""

import sys
import requests
import json
sys.path.append('backend')

from backend.utils.session import get_breeze

def test_option_chain_api():
    """Test the option chain API endpoints."""
    base_url = "http://127.0.0.1:8000"
    
    print("Testing Option Chain API...")
    
    # Test Nifty option chain
    try:
        response = requests.get(f"{base_url}/api/option-chain/nifty-strikes")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Nifty option chain: {data.get('success', False)}")
            if data.get('success'):
                calls = data.get('calls', [])
                puts = data.get('puts', [])
                print(f"   Calls: {len(calls)}, Puts: {len(puts)}")
                if calls:
                    print(f"   Sample call: Strike {calls[0].get('strike_price')}, LTP {calls[0].get('ltp')}")
        else:
            print(f"❌ Nifty option chain failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Nifty option chain error: {e}")
    
    # Test expiry dates
    try:
        response = requests.get(f"{base_url}/api/option-chain/expiry-dates?index=NIFTY")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Expiry dates: {data.get('success', False)}")
            if data.get('success'):
                dates = data.get('dates', [])
                print(f"   Available dates: {len(dates)}")
                for date in dates[:3]:  # Show first 3
                    print(f"   - {date.get('display')} ({date.get('iso_date')})")
        else:
            print(f"❌ Expiry dates failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Expiry dates error: {e}")
    
    # Test option chain subscription
    try:
        response = requests.post(f"{base_url}/api/option-chain/subscribe", params={
            "stock_code": "NIFTY",
            "exchange_code": "NFO",
            "product_type": "options",
            "right": "both",
            "expiry_date": "2025-09-02T06:00:00.000Z",
            "limit": 10
        })
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Option chain subscription: {data.get('success', False)}")
            if data.get('success'):
                print(f"   Subscribed count: {data.get('subscribed_count', 0)}")
        else:
            print(f"❌ Option chain subscription failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Option chain subscription error: {e}")

def test_breeze_connection():
    """Test Breeze connection."""
    print("\nTesting Breeze Connection...")
    
    try:
        breeze = get_breeze()
        if breeze:
            print("✅ Breeze service available")
            
            # Test getting Nifty quote
            try:
                quote = breeze.client.get_quotes(
                    stock_code="NIFTY",
                    exchange_code="NSE",
                    product_type="cash"
                )
                if quote and quote.get("Success"):
                    success_data = quote.get("Success", [])
                    if success_data:
                        ltp = success_data[0].get("ltp", 0)
                        print(f"✅ Nifty LTP: {ltp}")
                    else:
                        print("❌ No Nifty data in response")
                else:
                    print("❌ Nifty quote failed")
            except Exception as e:
                print(f"❌ Nifty quote error: {e}")
        else:
            print("❌ No Breeze service available")
    except Exception as e:
        print(f"❌ Breeze connection error: {e}")

if __name__ == "__main__":
    test_breeze_connection()
    test_option_chain_api()
