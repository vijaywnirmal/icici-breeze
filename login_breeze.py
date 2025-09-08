#!/usr/bin/env python3
"""
Script to login to Breeze and establish a session for option chain data.
"""

import sys
import os
sys.path.append('backend')

from backend.utils.session import get_breeze, set_breeze, clear_session
from backend.services.breeze_service import BreezeService
from backend.utils.config import settings

def login_to_breeze():
    """Login to Breeze and establish a session."""
    print("🔐 Breeze Login Script")
    print("=" * 40)
    
    # Clear any existing session
    print("1. Clearing existing session...")
    clear_session()
    
    # Get credentials from environment or user input
    api_key = settings.breeze_api_key
    api_secret = settings.breeze_api_secret
    
    if not api_key or not api_secret:
        print("❌ Breeze credentials not found in environment variables")
        print("Please set BREEZE_API_KEY and BREEZE_API_SECRET in your .env file")
        return False
    
    print(f"✅ API Key: {api_key[:10]}...")
    print(f"✅ API Secret: {'*' * len(api_secret)}")
    
    # Get session token from user
    session_token = input("\nEnter your Breeze session token: ").strip()
    if not session_token:
        print("❌ Session token is required")
        return False
    
    try:
        # Create Breeze service
        print("\n2. Creating Breeze service...")
        breeze_service = BreezeService(api_key=api_key)
        
        # Generate session
        print("3. Generating session...")
        result = breeze_service.login_and_fetch_profile(
            api_secret=api_secret,
            session_key=session_token
        )
        
        if result.success:
            print("✅ Login successful!")
            print(f"   User: {result.profile.get('first_name', 'Unknown')} {result.profile.get('last_name', '')}")
            print(f"   Session Token: {breeze_service.client.session_token[:20]}...")
            
            # Save session
            print("4. Saving session...")
            set_breeze(breeze_service)
            print("✅ Session saved successfully!")
            
            return True
        else:
            print(f"❌ Login failed: {result.message}")
            if result.error:
                print(f"   Error: {result.error}")
            return False
            
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False

def test_session():
    """Test the established session."""
    print("\n🧪 Testing Session")
    print("=" * 20)
    
    breeze = get_breeze()
    if not breeze:
        print("❌ No session found")
        return False
    
    if not breeze.client.session_token:
        print("❌ No session token found")
        return False
    
    print("✅ Session found")
    print(f"   API Key: {breeze.client.api_key[:10]}...")
    print(f"   Session Token: {breeze.client.session_token[:20]}...")
    
    # Test a simple API call
    try:
        print("\n5. Testing API call...")
        quote = breeze.client.get_quotes(
            stock_code="NIFTY",
            exchange_code="NSE",
            product_type="cash"
        )
        
        if quote and quote.get("Success"):
            success_data = quote.get("Success", [])
            if success_data:
                ltp = success_data[0].get("ltp", 0)
                print(f"✅ API test successful! NIFTY LTP: {ltp}")
                return True
            else:
                print("❌ No data in API response")
                return False
        else:
            print("❌ API call failed")
            return False
            
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def main():
    """Main function."""
    print("🚀 Starting Breeze Login Process")
    print("=" * 50)
    
    # Step 1: Login
    if not login_to_breeze():
        print("\n❌ Login failed. Please check your credentials and try again.")
        return
    
    # Step 2: Test session
    if not test_session():
        print("\n❌ Session test failed. Please try logging in again.")
        return
    
    print("\n" + "=" * 50)
    print("🎉 Breeze Login Successful!")
    print("\n📝 Next Steps:")
    print("   1. The session is now saved and will persist across server restarts")
    print("   2. You can now use the option chain functionality")
    print("   3. The session will expire in 24 hours")
    print("   4. If you need to login again, run this script")

if __name__ == "__main__":
    main()
