#!/usr/bin/env python3
"""
Test script to check data availability for ICICI Breeze Trading Platform.

This script checks what data is already available without requiring database connection.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def check_security_master_files():
    """Check SecurityMaster files availability."""
    print("🔍 Checking SecurityMaster files...")
    
    security_master_dir = Path("SecurityMaster")
    if not security_master_dir.exists():
        print("❌ SecurityMaster directory not found")
        return False
    
    required_files = [
        "NSEScripMaster.txt",
        "BSEScripMaster.txt",
        "FONSEScripMaster.txt",
        "FOBSEScripMaster.txt",
        "CDNSEScripMaster.txt"
    ]
    
    all_exist = True
    for filename in required_files:
        file_path = security_master_dir / filename
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✅ {filename}: {size:,} bytes")
        else:
            print(f"❌ {filename}: Not found")
            all_exist = False
    
    return all_exist


def check_holidays_csv():
    """Check holidays CSV file availability."""
    print("\n🔍 Checking holidays CSV file...")
    
    holidays_csv = Path("src/HolidaycalenderData.csv")
    if holidays_csv.exists():
        size = holidays_csv.stat().st_size
        print(f"✅ HolidaycalenderData.csv: {size:,} bytes")
        
        # Try to read and show sample data
        try:
            df = pd.read_csv(holidays_csv)
            print(f"   📊 Contains {len(df)} holiday records")
            print(f"   📅 Date range: {df['Date'].min()} to {df['Date'].max()}")
            return True
        except Exception as e:
            print(f"   ⚠️  Could not read CSV: {e}")
            return False
    else:
        print("❌ HolidaycalenderData.csv: Not found")
        return False


def check_env_file():
    """Check environment file availability."""
    print("\n🔍 Checking environment configuration...")
    
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file exists")
        
        # Check for required environment variables
        with open(env_file, 'r') as f:
            content = f.read()
        
        required_vars = [
            "BREEZE_API_KEY",
            "BREEZE_API_SECRET", 
            "BREEZE_SESSION_TOKEN",
            "POSTGRES_DSN"
        ]
        
        for var in required_vars:
            if var in content:
                print(f"   ✅ {var}: Configured")
            else:
                print(f"   ❌ {var}: Not configured")
        
        return True
    else:
        print("❌ .env file not found")
        print("   💡 Copy env.example to .env and configure your credentials")
        return False


def check_python_dependencies():
    """Check if required Python packages are available."""
    print("\n🔍 Checking Python dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn", 
        "sqlalchemy",
        "pandas",
        "loguru",
        "nselib",
        "requests"
    ]
    
    all_available = True
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}: Available")
        except ImportError:
            print(f"❌ {package}: Not installed")
            all_available = False
    
    return all_available


def show_data_summary():
    """Show a summary of available data."""
    print("\n" + "="*60)
    print("📊 DATA AVAILABILITY SUMMARY")
    print("="*60)
    
    # Check SecurityMaster files
    sm_available = check_security_master_files()
    
    # Check holidays CSV
    holidays_available = check_holidays_csv()
    
    # Check environment
    env_available = check_env_file()
    
    # Check dependencies
    deps_available = check_python_dependencies()
    
    print("\n" + "="*60)
    print("📋 RECOMMENDATIONS")
    print("="*60)
    
    if not sm_available:
        print("🔧 Action needed: Download SecurityMaster files")
        print("   Run: python -c \"from src.utils.security_master import download_and_extract_security_master; download_and_extract_security_master()\"")
    
    if not holidays_available:
        print("🔧 Action needed: Holidays CSV file is missing")
        print("   Check if src/HolidaycalenderData.csv exists")
    
    if not env_available:
        print("🔧 Action needed: Configure environment variables")
        print("   Copy env.example to .env and set your ICICI Breeze credentials")
    
    if not deps_available:
        print("🔧 Action needed: Install missing Python packages")
        print("   Run: pip install -r requirements.txt")
    
    if all([sm_available, holidays_available, env_available, deps_available]):
        print("✅ All basic data is available!")
        print("   You can now run: python fetch_all_data.py")
        print("   Or start the server: python -m uvicorn src.app:app --host 127.0.0.1 --port 8000")


def main():
    """Main function."""
    print("🚀 ICICI Breeze Trading Platform - Data Availability Check")
    print("="*60)
    
    show_data_summary()


if __name__ == "__main__":
    main()
