#!/usr/bin/env python3
"""
Basic data fetching script for ICICI Breeze Trading Platform.

This script fetches basic data that doesn't require database connection:
1. SecurityMaster files (instruments data)
2. Market holidays CSV
3. Basic setup files
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from loguru import logger
from src.utils.security_master import download_and_extract_security_master
from src.utils.holidays_csv import load_holidays


def setup_logging():
    """Configure logging for the script."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )


def fetch_security_master_files(security_master_dir: Optional[Path] = None) -> bool:
    """Download SecurityMaster files."""
    logger.info("Starting SecurityMaster files download...")
    
    try:
        if security_master_dir is None:
            security_master_dir = Path.cwd() / "SecurityMaster"
        
        # Ensure directory exists
        security_master_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if files already exist
        required_files = [
            security_master_dir / "NSEScripMaster.txt",
            security_master_dir / "BSEScripMaster.txt"
        ]
        
        if all(f.exists() for f in required_files):
            logger.info("SecurityMaster files already exist")
            return True
        
        # Download files
        logger.info("Downloading SecurityMaster files...")
        download_and_extract_security_master(destination_dir=security_master_dir)
        
        # Verify files were downloaded
        if all(f.exists() for f in required_files):
            logger.success("SecurityMaster files downloaded successfully")
            return True
        else:
            logger.error("Some SecurityMaster files are missing after download")
            return False
            
    except Exception as e:
        logger.error(f"Failed to download SecurityMaster files: {e}")
        return False


def check_holidays_data() -> bool:
    """Check if holidays data is available."""
    logger.info("Checking holidays data...")
    
    try:
        holidays = load_holidays()
        logger.success(f"Holidays data available: {len(holidays)} holidays loaded")
        return True
        
    except Exception as e:
        logger.error(f"Failed to load holidays data: {e}")
        return False


def check_existing_files():
    """Check what files already exist."""
    logger.info("Checking existing files...")
    
    # Check SecurityMaster directory
    security_master_dir = Path.cwd() / "SecurityMaster"
    if security_master_dir.exists():
        nse_file = security_master_dir / "NSEScripMaster.txt"
        bse_file = security_master_dir / "BSEScripMaster.txt"
        
        logger.info(f"SecurityMaster directory: {security_master_dir}")
        logger.info(f"NSE file exists: {nse_file.exists()}")
        logger.info(f"BSE file exists: {bse_file.exists()}")
        
        if nse_file.exists():
            size = nse_file.stat().st_size
            logger.info(f"NSE file size: {size:,} bytes")
        if bse_file.exists():
            size = bse_file.stat().st_size
            logger.info(f"BSE file size: {size:,} bytes")
    else:
        logger.info("SecurityMaster directory does not exist")
    
    # Check holidays CSV
    holidays_csv = Path("src/HolidaycalenderData.csv")
    if holidays_csv.exists():
        size = holidays_csv.stat().st_size
        logger.info(f"Holidays CSV exists: {holidays_csv} ({size:,} bytes)")
    else:
        logger.info("Holidays CSV does not exist")


def main():
    """Main function to orchestrate basic data fetching."""
    setup_logging()
    
    logger.info("Starting basic data fetch for ICICI Breeze Trading Platform")
    
    # Check existing files
    check_existing_files()
    
    # Fetch basic data
    success_count = 0
    total_tasks = 2
    
    # 1. Fetch SecurityMaster files
    if fetch_security_master_files():
        success_count += 1
    
    # 2. Check holidays data
    if check_holidays_data():
        success_count += 1
    
    # Final status
    logger.info("=" * 60)
    logger.info(f"Basic data fetch completed: {success_count}/{total_tasks} tasks successful")
    
    if success_count == total_tasks:
        logger.success("All basic data fetched successfully!")
        check_existing_files()  # Show final status
        return 0
    else:
        logger.warning(f"Some tasks failed. {total_tasks - success_count} tasks failed.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
