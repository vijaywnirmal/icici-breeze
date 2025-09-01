#!/usr/bin/env python3
"""
Comprehensive data fetching script for ICICI Breeze Trading Platform.

This script fetches and populates all required data for PostgreSQL tables:
1. Instruments (SecurityMaster files)
2. Nifty50 list
3. Market holidays
4. Historical data (if needed)
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from loguru import logger
from src.utils.postgres import ensure_tables, get_engine
from src.utils.instruments_first_run import ensure_instruments_first_run
from src.utils.nifty50_service import refresh_nifty50_list
from src.utils.holidays_csv import load_holidays
from src.utils.security_master import download_and_extract_security_master


def setup_logging():
    """Configure logging for the script."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )


def check_database_connection() -> bool:
    """Check if database connection is available."""
    engine = get_engine()
    if engine is None:
        logger.error("No database connection configured. Please set POSTGRES_DSN in your .env file.")
        return False
    
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def fetch_instruments_data(security_master_dir: Optional[Path] = None) -> bool:
    """Fetch and populate instruments data from SecurityMaster files."""
    logger.info("Starting instruments data fetch...")
    
    try:
        if security_master_dir is None:
            security_master_dir = Path.cwd() / "SecurityMaster"
        
        # Ensure SecurityMaster directory exists
        security_master_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if SecurityMaster files exist, download if needed
        required_files = [
            security_master_dir / "NSEScripMaster.txt",
            security_master_dir / "BSEScripMaster.txt"
        ]
        
        if not all(f.exists() for f in required_files):
            logger.info("SecurityMaster files not found. Downloading...")
            download_and_extract_security_master(destination_dir=security_master_dir)
        
        # Populate instruments table
        ensure_instruments_first_run(security_master_dir)
        logger.success("Instruments data fetch completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to fetch instruments data: {e}")
        return False


def fetch_nifty50_data() -> bool:
    """Fetch and populate Nifty50 list data."""
    logger.info("Starting Nifty50 data fetch...")
    
    try:
        count = refresh_nifty50_list()
        logger.success(f"Nifty50 data fetch completed successfully. {count} stocks loaded.")
        return True
        
    except Exception as e:
        logger.error(f"Failed to fetch Nifty50 data: {e}")
        return False


def fetch_market_holidays() -> bool:
    """Fetch and populate market holidays data."""
    logger.info("Starting market holidays data fetch...")
    
    try:
        # Load holidays from CSV
        holidays = load_holidays()
        logger.success(f"Market holidays data fetch completed successfully. {len(holidays)} holidays loaded.")
        return True
        
    except Exception as e:
        logger.error(f"Failed to fetch market holidays data: {e}")
        return False


def check_table_data():
    """Check what data exists in the tables."""
    engine = get_engine()
    if engine is None:
        return
    
    try:
        with engine.connect() as conn:
            # Check instruments table
            result = conn.execute("SELECT COUNT(*) FROM instruments")
            instruments_count = result.fetchone()[0]
            logger.info(f"Instruments table: {instruments_count} rows")
            
            # Check nifty50_list table
            result = conn.execute("SELECT COUNT(*) FROM nifty50_list")
            nifty50_count = result.fetchone()[0]
            logger.info(f"Nifty50 list table: {nifty50_count} rows")
            
            # Check market_holidays table
            result = conn.execute("SELECT COUNT(*) FROM market_holidays")
            holidays_count = result.fetchone()[0]
            logger.info(f"Market holidays table: {holidays_count} rows")
            
            # Check quotes_cache table
            result = conn.execute("SELECT COUNT(*) FROM quotes_cache")
            quotes_count = result.fetchone()[0]
            logger.info(f"Quotes cache table: {quotes_count} rows")
            
    except Exception as e:
        logger.error(f"Failed to check table data: {e}")


def main():
    """Main function to orchestrate data fetching."""
    setup_logging()
    
    logger.info("Starting comprehensive data fetch for ICICI Breeze Trading Platform")
    
    # Check database connection
    if not check_database_connection():
        logger.error("Cannot proceed without database connection")
        return 1
    
    # Ensure tables exist
    logger.info("Ensuring database tables exist...")
    ensure_tables()
    
    # Check existing data
    logger.info("Checking existing data...")
    check_table_data()
    
    # Fetch all data
    success_count = 0
    total_tasks = 3
    
    # 1. Fetch instruments data
    if fetch_instruments_data():
        success_count += 1
    
    # 2. Fetch Nifty50 data
    if fetch_nifty50_data():
        success_count += 1
    
    # 3. Fetch market holidays data
    if fetch_market_holidays():
        success_count += 1
    
    # Final status
    logger.info("=" * 60)
    logger.info(f"Data fetch completed: {success_count}/{total_tasks} tasks successful")
    
    if success_count == total_tasks:
        logger.success("All data fetched successfully!")
        check_table_data()  # Show final counts
        return 0
    else:
        logger.warning(f"Some tasks failed. {total_tasks - success_count} tasks failed.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
