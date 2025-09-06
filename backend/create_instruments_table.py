#!/usr/bin/env python3
"""
Create new instruments table with exact requirements:
- Replace existing instruments table
- Columns: Token, ShortName, Series, CompanyName, ISINCode, ExchangeCode
- Match nsetools stock list on ExchangeCode
- Save only matching stocks to database
"""

import sys
import pandas as pd
from pathlib import Path
from typing import Dict, List

# Add backend to path for imports
sys.path.insert(0, 'backend')

from utils.postgres import get_conn
from utils.response import log_exception
from loguru import logger
from sqlalchemy import text


def download_and_extract_data() -> bool:
    """Download and extract SecurityMaster.zip if not already present."""
    try:
        SECURITY_MASTER_DIR = Path("SecurityMaster")
        NSE_SCRIP_FILE = SECURITY_MASTER_DIR / "NSEScripMaster.txt"
        
        if NSE_SCRIP_FILE.exists():
            logger.info("NSEScripMaster.txt already exists, skipping download")
            return True
            
        logger.info("Downloading SecurityMaster.zip...")
        import requests
        import zipfile
        
        SECURITY_MASTER_URL = "https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip"
        SECURITY_MASTER_ZIP = SECURITY_MASTER_DIR / "SecurityMaster.zip"
        
        SECURITY_MASTER_DIR.mkdir(exist_ok=True)
        
        response = requests.get(SECURITY_MASTER_URL, stream=True)
        response.raise_for_status()
        
        with open(SECURITY_MASTER_ZIP, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        with zipfile.ZipFile(SECURITY_MASTER_ZIP, 'r') as zip_ref:
            zip_ref.extractall(SECURITY_MASTER_DIR)
        
        logger.info("Download and extraction completed")
        return True
        
    except Exception as exc:
        log_exception(exc, context="download_and_extract_data")
        return False


def get_nse_stock_list() -> List[str]:
    """Get active NSE stock list from nsetools."""
    try:
        logger.info("Fetching NSE stock list from nsetools...")
        from nsetools import Nse
        
        nse = Nse()
        codes = nse.get_stock_codes()
        
        if isinstance(codes, list):
            stock_list = codes
        elif isinstance(codes, dict):
            stock_list = list(codes.keys())
        else:
            logger.error(f"Unexpected format from nsetools: {type(codes)}")
            return []
        
        logger.info(f"Fetched {len(stock_list)} active NSE stocks")
        return stock_list
        
    except Exception as exc:
        log_exception(exc, context="get_nse_stock_list")
        return []


def load_and_filter_instruments() -> pd.DataFrame:
    """Load NSEScripMaster.txt and filter by nsetools stock list."""
    try:
        logger.info("Loading NSEScripMaster.txt...")
        
        # Load the data
        df = pd.read_csv("SecurityMaster/NSEScripMaster.txt", sep=',', low_memory=False)
        logger.info(f"Loaded {len(df)} records from NSEScripMaster.txt")
        
        # Get the exact columns we need
        required_columns = {
            'Token': 'Token',
            ' "ShortName"': 'ShortName', 
            ' "CompanyName"': 'CompanyName',
            ' "ISINCode"': 'ISINCode',
            ' "ExchangeCode"': 'ExchangeCode'
        }
        
        # Check if all required columns exist
        missing_columns = [col for col in required_columns.keys() if col not in df.columns]
        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            return pd.DataFrame()
        
        # Select only the required columns
        instruments_df = df[list(required_columns.keys())].copy()
        
        # Rename columns to clean names
        instruments_df = instruments_df.rename(columns=required_columns)
        
        # Clean the data
        instruments_df = instruments_df.dropna(subset=['Token', 'ExchangeCode'])
        instruments_df['Token'] = instruments_df['Token'].astype(str)
        
        logger.info(f"After cleaning: {len(instruments_df)} records")
        
        # Get NSE stock list for filtering
        nse_stocks = get_nse_stock_list()
        if not nse_stocks:
            logger.error("No NSE stock list available")
            return pd.DataFrame()
        
        # Convert to uppercase for case-insensitive matching
        nse_stocks_upper = [stock.upper() for stock in nse_stocks]
        instruments_df['ExchangeCode_upper'] = instruments_df['ExchangeCode'].str.upper()
        
        # Filter to only include stocks that exist in nsetools
        filtered_df = instruments_df[instruments_df['ExchangeCode_upper'].isin(nse_stocks_upper)].copy()
        
        # Remove the temporary column
        filtered_df = filtered_df.drop('ExchangeCode_upper', axis=1)
        
        logger.info(f"After filtering by nsetools: {len(filtered_df)} matching records")
        
        # Remove duplicates based on Token
        filtered_df = filtered_df.drop_duplicates(subset=['Token'])
        
        logger.info(f"Final instruments: {len(filtered_df)} unique records")
        
        return filtered_df
        
    except Exception as exc:
        log_exception(exc, context="load_and_filter_instruments")
        return pd.DataFrame()


def create_new_instruments_table(instruments_df: pd.DataFrame) -> bool:
    """Update existing instruments table with new data."""
    try:
        logger.info("Updating instruments table...")
        
        with get_conn() as conn:
            if conn is None:
                logger.error("No database connection available")
                return False
            
            # Create instruments table if it doesn't exist
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS instruments (
                    token VARCHAR PRIMARY KEY,
                    short_name VARCHAR,
                    company_name VARCHAR,
                    isin_code VARCHAR,
                    exchange_code VARCHAR,
                    websocket_enabled BOOLEAN DEFAULT TRUE,
                    last_update TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            logger.info("Ensured instruments table exists")
            
            # Add indexes for performance (IF NOT EXISTS)
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_instruments_exchange_code ON instruments(exchange_code);
                CREATE INDEX IF NOT EXISTS idx_instruments_websocket_enabled ON instruments(websocket_enabled);
                CREATE INDEX IF NOT EXISTS idx_instruments_company_name ON instruments(company_name);
            """))
            logger.info("Ensured performance indexes exist")
            
            # Clear existing data and insert new data
            conn.execute(text("DELETE FROM instruments"))
            logger.info("Cleared existing instruments data")
            
            # Insert data
            inserted_count = 0
            for _, row in instruments_df.iterrows():
                try:
                    conn.execute(text("""
                        INSERT INTO instruments (
                            token, short_name, company_name, 
                            isin_code, exchange_code, websocket_enabled, last_update
                        ) VALUES (
                            :token, :short_name, :company_name,
                            :isin_code, :exchange_code, :websocket_enabled, NOW()
                        )
                    """), {
                        "token": str(row['Token']),
                        "short_name": row['ShortName'],
                        "company_name": row['CompanyName'],
                        "isin_code": row['ISINCode'],
                        "exchange_code": row['ExchangeCode'],
                        "websocket_enabled": True
                    })
                    inserted_count += 1
                    
                except Exception as exc:
                    log_exception(exc, context="insert_instrument", token=row['Token'])
                    continue
            
            conn.commit()
            logger.info(f"Inserted {inserted_count} instruments into database")
            
            return inserted_count > 0
            
    except Exception as exc:
        log_exception(exc, context="create_new_instruments_table")
        return False





def main():
    """Main execution function."""
    logger.info("Starting instruments table creation...")
    
    try:
        # Step 1: Download and extract data if needed
        if not download_and_extract_data():
            logger.error("Failed to download/extract data")
            return False
        
        # Step 2: Load and filter instruments
        instruments_df = load_and_filter_instruments()
        if instruments_df.empty:
            logger.error("No instruments data to process")
            return False
        
        # Step 3: Create new instruments table
        if not create_new_instruments_table(instruments_df):
            logger.error("Failed to create instruments table")
            return False
        
        logger.info("Instruments table creation completed successfully!")
        return True
        
    except Exception as exc:
        log_exception(exc, context="main")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
