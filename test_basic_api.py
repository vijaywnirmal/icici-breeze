#!/usr/bin/env python3
"""Test basic API endpoints to debug option chain issue."""

import requests
import json

def test_basic_endpoints():
    """Test basic API endpoints."""
    base_url = "http://127.0.0.1:8000"
    
    print("🔍 Testing Basic API Endpoints")
    print("=" * 40)
    
    # Test 1: Health check
    try:
        print("1. Testing health check...")
        response = requests.get(f"{base_url}/api/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Health check passed")
        else:
            print(f"   ❌ Health check failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
    
    # Test 2: NIFTY strikes
    try:
        print("\n2. Testing NIFTY strikes...")
        response = requests.get(f"{base_url}/api/option-chain/nifty-strikes")
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success', False)}")
            if data.get('success'):
                print(f"   ✅ NIFTY strikes: {len(data.get('calls', []))} calls, {len(data.get('puts', []))} puts")
                print(f"   Underlying price: {data.get('underlying_price', 'N/A')}")
            else:
                print(f"   ❌ API Error: {data.get('error', 'Unknown error')}")
        else:
            print(f"   ❌ HTTP Error: {response.text}")
    except Exception as e:
        print(f"   ❌ NIFTY strikes error: {e}")
    
    # Test 3: Option subscription
    try:
        print("\n3. Testing option subscription...")
        payload = {
            "stock_code": "NIFTY",
            "exchange_code": "NFO",
            "product_type": "options",
            "right": "both",
            "expiry_date": "2025-09-10T06:00:00.000Z",
            "limit": 3
        }
        
        response = requests.post(
            f"{base_url}/api/option-chain/subscribe",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success', False)}")
            if data.get('success'):
                print(f"   ✅ Subscription successful: {data.get('subscribed_count', 0)} subscriptions")
                print(f"   Strikes: {data.get('strikes', [])}")
            else:
                print(f"   ❌ Subscription failed: {data.get('error', 'Unknown error')}")
        else:
            print(f"   ❌ HTTP Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Subscription error: {e}")

if __name__ == "__main__":
    test_basic_endpoints()
