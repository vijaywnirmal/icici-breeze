# Data Fetching Guide for ICICI Breeze Trading Platform

This guide explains how to fetch and populate all required data for the PostgreSQL tables in the ICICI Breeze Trading Platform.

## Prerequisites

1. **Database Setup**: Ensure PostgreSQL is running and `POSTGRES_DSN` is configured in your `.env` file
2. **Python Dependencies**: Install all required packages from `requirements.txt`
3. **ICICI Breeze Credentials**: Ensure `BREEZE_API_KEY`, `BREEZE_API_SECRET`, and `BREEZE_SESSION_TOKEN` are set in `.env`

## Available Data Files

### ✅ Already Available
- **SecurityMaster Files**: Located in `SecurityMaster/` directory
  - `NSEScripMaster.txt` (1.2MB) - NSE instruments
  - `BSEScripMaster.txt` (2.4MB) - BSE instruments
  - `FONSEScripMaster.txt` (18MB) - NSE F&O instruments
  - `FOBSEScripMaster.txt` (1.1MB) - BSE F&O instruments
  - `CDNSEScripMaster.txt` (468KB) - Currency derivatives

- **Market Holidays**: `src/HolidaycalenderData.csv` - Contains market holidays from 2021-2025

## PostgreSQL Tables Structure

The application uses the following PostgreSQL tables:

### 1. `instruments` - Security Master Data
- **Purpose**: Stores all trading instruments (stocks, indices, F&O)
- **Source**: SecurityMaster files from ICICI
- **Columns**: token, symbol, short_name, company_name, series, isin, lot_size, exchange, raw (JSONB)

### 2. `nifty50_list` - Nifty 50 Constituents
- **Purpose**: Stores Nifty 50 index constituents
- **Source**: NSE website via nselib
- **Columns**: symbol, stock_code, company_name, exchange, weight, sector

### 3. `market_holidays` - Market Holidays
- **Purpose**: Stores market holidays for trading calendar
- **Source**: HolidaycalenderData.csv
- **Columns**: date, name, source, updated_at

### 4. `quotes_cache` - Live Quotes Cache
- **Purpose**: Caches live market quotes
- **Source**: Breeze API live data
- **Columns**: symbol, data (JSONB), updated_at

### 5. `api_usage` - API Usage Tracking
- **Purpose**: Tracks Breeze API usage
- **Source**: Application usage
- **Columns**: date, method, count, updated_at

### 6. `historical_data` - Historical OHLC Cache
- **Purpose**: Caches historical price data
- **Source**: Breeze API historical data
- **Columns**: symbol, date, ohlc (JSONB)

### 7. `backtests` - Backtest Results
- **Purpose**: Stores backtest summaries
- **Source**: Strategy backtesting
- **Columns**: id, user_id, symbol, strategy, params, start_date, end_date, summary

### 8. `trades` - Individual Trades
- **Purpose**: Stores individual trades from backtests
- **Source**: Strategy backtesting
- **Columns**: backtest_id, trade_no, entry_date, exit_date, entry_price, exit_price, pnl

### 9. `strategies` - Strategy Catalog
- **Purpose**: Stores strategy definitions
- **Source**: Strategy builder
- **Columns**: name, description, json (JSONB)

## Data Fetching Commands

### Option 1: Using the Comprehensive Script (Recommended)

```bash
# Run the comprehensive data fetching script
python fetch_all_data.py
```

This script will:
1. Check database connection
2. Create all required tables
3. Populate instruments from SecurityMaster files
4. Fetch Nifty50 constituents
5. Load market holidays
6. Show data counts for all tables

### Option 2: Manual Step-by-Step

#### Step 1: Ensure Database Tables Exist
```python
from src.utils.postgres import ensure_tables
ensure_tables()
```

#### Step 2: Populate Instruments Table
```python
from src.utils.instruments_first_run import ensure_instruments_first_run
from pathlib import Path

# This will download SecurityMaster files if needed and populate instruments table
ensure_instruments_first_run(Path("SecurityMaster"))
```

#### Step 3: Fetch Nifty50 List
```python
from src.utils.nifty50_service import refresh_nifty50_list

# This will fetch current Nifty50 constituents from NSE
count = refresh_nifty50_list()
print(f"Loaded {count} Nifty50 stocks")
```

#### Step 4: Load Market Holidays
```python
from src.utils.holidays_csv import load_holidays

# This will load holidays from the CSV file
holidays = load_holidays()
print(f"Loaded {len(holidays)} market holidays")
```

### Option 3: Using Individual CLI Commands

```bash
# Populate instruments (downloads SecurityMaster if needed)
python -m src.utils.instruments_first_run

# Refresh Nifty50 list
python -c "from src.utils.nifty50_service import refresh_nifty50_list; print(refresh_nifty50_list())"
```

## Data Verification

After fetching data, you can verify the data using these commands:

### Check Table Row Counts
```python
from src.utils.postgres import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    # Check instruments
    result = conn.execute(text("SELECT COUNT(*) FROM instruments"))
    print(f"Instruments: {result.fetchone()[0]} rows")
    
    # Check Nifty50
    result = conn.execute(text("SELECT COUNT(*) FROM nifty50_list"))
    print(f"Nifty50: {result.fetchone()[0]} rows")
    
    # Check holidays
    result = conn.execute(text("SELECT COUNT(*) FROM market_holidays"))
    print(f"Holidays: {result.fetchone()[0]} rows")
```

### Expected Data Volumes
- **Instruments**: ~50,000+ rows (all NSE/BSE instruments)
- **Nifty50**: ~50 rows (current constituents)
- **Market Holidays**: ~70+ rows (2021-2025 holidays)
- **Quotes Cache**: Variable (populated during live trading)
- **API Usage**: Variable (populated during API usage)

## Troubleshooting

### Database Connection Issues
- Ensure `POSTGRES_DSN` is correctly set in `.env`
- Verify PostgreSQL is running and accessible
- Check firewall settings if connecting to remote database

### SecurityMaster Download Issues
- Check internet connection
- Verify ICICI Breeze credentials are valid
- Check disk space (requires ~50MB for all files)

### Nifty50 Fetch Issues
- Ensure `nselib` package is installed
- Check internet connection for NSE website access
- Verify the NSE website is accessible

### Permission Issues
- Ensure write permissions to `SecurityMaster/` directory
- Check database user permissions for table creation and data insertion

## Data Refresh Schedule

### Daily Refresh (Recommended)
- **Nifty50 List**: Refresh daily at 8:00 AM IST
- **Quotes Cache**: Automatically refreshed during market hours
- **API Usage**: Automatically tracked

### Weekly Refresh
- **Instruments**: Refresh weekly (SecurityMaster files are updated weekly)
- **Market Holidays**: Refresh quarterly or when new holidays are announced

### Manual Refresh
- **Historical Data**: Refresh as needed for backtesting
- **Backtests**: Generated on-demand
- **Strategies**: Created/updated as needed

## API Usage Considerations

- **Breeze API Limits**: 100 calls/minute, 5000 calls/day
- **Historical Data**: Cached to reduce API usage
- **Live Quotes**: Use WebSocket when possible to reduce polling
- **Usage Tracking**: Monitor via `api_usage` table

## Next Steps

After fetching all data:

1. **Start the Backend Server**:
   ```bash
   python -m uvicorn src.app:app --host 127.0.0.1 --port 8000
   ```

2. **Start the Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

3. **Verify Live Data**:
   - Check ticker bar shows live prices
   - Verify WebSocket connections for real-time data
   - Test strategy builder with historical data

## Support

If you encounter issues:
1. Check the logs in `logs/` directory
2. Verify all environment variables are set correctly
3. Ensure all Python dependencies are installed
4. Check database connectivity and permissions
