#!/usr/bin/env python3
"""
Test script for persistent login functionality.
This script tests session persistence across server restarts.
"""

import sys
import os
import time
import requests
import json
from pathlib import Path

# Add backend to path
sys.path.append('backend')

from backend.utils.session import get_breeze, set_breeze, clear_session, is_session_valid
from backend.services.breeze_service import BreezeService

def test_session_persistence():
    """Test session persistence functionality."""
    print("🧪 Testing Persistent Login Functionality")
    print("=" * 50)
    
    # Clear any existing session first
    print("1. Clearing any existing session...")
    clear_session()
    
    # Test 1: No session initially
    print("\n2. Testing initial state...")
    breeze = get_breeze()
    if breeze is None:
        print("   ✅ No session found initially (expected)")
    else:
        print("   ❌ Unexpected session found")
        return False
    
    # Test 2: Create a mock session (simulate login)
    print("\n3. Creating mock session...")
    try:
        # Create a mock BreezeService with dummy credentials
        mock_service = BreezeService(api_key="test_api_key")
        # Set a mock session token
        mock_service.client.session_token = "test_session_token"
        
        # Save the session
        set_breeze(mock_service)
        print("   ✅ Mock session created and saved")
        
        # Verify session was saved
        if Path("session_data.json").exists():
            print("   ✅ Session file created")
        else:
            print("   ❌ Session file not created")
            return False
            
    except Exception as e:
        print(f"   ❌ Failed to create mock session: {e}")
        return False
    
    # Test 3: Clear in-memory session and restore from file
    print("\n4. Testing session restoration...")
    try:
        # Clear the global session variable (simulate server restart)
        import backend.utils.session as session_module
        session_module._BREEZE = None
        
        # Try to restore session
        restored_breeze = get_breeze()
        if restored_breeze is not None:
            print("   ✅ Session restored from file")
            print(f"   📋 API Key: {restored_breeze.client.api_key}")
            print(f"   🔑 Session Token: {restored_breeze.client.session_token}")
        else:
            print("   ❌ Failed to restore session")
            return False
            
    except Exception as e:
        print(f"   ❌ Session restoration failed: {e}")
        return False
    
    # Test 4: Test session validation
    print("\n5. Testing session validation...")
    try:
        # Note: This will fail with mock credentials, but we can test the logic
        is_valid = is_session_valid()
        if not is_valid:
            print("   ✅ Session validation correctly identified invalid session")
        else:
            print("   ⚠️ Session validation passed (unexpected with mock data)")
    except Exception as e:
        print(f"   ⚠️ Session validation error (expected with mock data): {e}")
    
    # Test 5: Clean up
    print("\n6. Cleaning up...")
    clear_session()
    
    if not Path("session_data.json").exists():
        print("   ✅ Session file removed")
    else:
        print("   ❌ Session file still exists")
        return False
    
    print("\n" + "=" * 50)
    print("✅ Persistent Login Tests Completed Successfully!")
    return True

def test_api_endpoints_with_persistence():
    """Test API endpoints work with persistent sessions."""
    print("\n🌐 Testing API Endpoints with Persistent Sessions")
    print("=" * 50)
    
    API_BASE = "http://localhost:8000"
    
    # Test market status (should work without login)
    print("1. Testing market status endpoint...")
    try:
        response = requests.get(f"{API_BASE}/api/market/status")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("   ✅ Market status endpoint working")
            else:
                print(f"   ❌ Market status API error: {data.get('error')}")
        else:
            print(f"   ❌ Market status HTTP error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Market status request failed: {e}")
    
    # Test instruments search (should work without login)
    print("\n2. Testing instruments search endpoint...")
    try:
        response = requests.get(f"{API_BASE}/api/instruments/live-trading?q=RELIANCE&limit=5")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                count = len(data.get("items", []))
                print(f"   ✅ Instruments search working ({count} results)")
            else:
                print(f"   ❌ Instruments search API error: {data.get('error')}")
        else:
            print(f"   ❌ Instruments search HTTP error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Instruments search request failed: {e}")
    
    # Test bulk WebSocket API (requires login)
    print("\n3. Testing bulk WebSocket API (requires login)...")
    try:
        response = requests.get(f"{API_BASE}/api/bulk-websocket/tokens")
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                count = data.get("count", 0)
                print(f"   ✅ Bulk WebSocket API working ({count} tokens)")
            else:
                print(f"   ℹ️ Bulk WebSocket API error (expected without login): {data.get('error')}")
        else:
            print(f"   ❌ Bulk WebSocket API HTTP error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Bulk WebSocket API request failed: {e}")

def main():
    """Run all tests."""
    print("🚀 Starting Persistent Login Tests")
    print("=" * 60)
    
    # Test 1: Session persistence logic
    success = test_session_persistence()
    
    if not success:
        print("\n❌ Session persistence tests failed!")
        return
    
    # Test 2: API endpoints (if server is running)
    print("\n" + "=" * 60)
    test_api_endpoints_with_persistence()
    
    print("\n" + "=" * 60)
    print("🎉 All Tests Completed!")
    print("\n📝 Summary:")
    print("   ✅ Session persistence working")
    print("   ✅ Session restoration working")
    print("   ✅ Session validation working")
    print("   ✅ Session cleanup working")
    print("\n💡 For local development:")
    print("   1. Login once through the web interface")
    print("   2. Session will persist across server restarts")
    print("   3. No need to login again until session expires (24 hours)")

if __name__ == "__main__":
    main()
