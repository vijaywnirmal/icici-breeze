from __future__ import annotations

import pandas as pd
from datetime import datetime
from sqlalchemy import text
from ..utils.postgres import get_conn

HOLIDAYS_TABLE = "market_holidays"


def fetch_nse_holidays_2025() -> pd.DataFrame:
    """
    Fetch NSE holidays for 2025 using nsepython.
    
    Returns:
        DataFrame with columns: date, day, name
    """
    try:
        from nsepython import holiday_master
        
        print("Fetching NSE holidays for 2025 using nsepython")
        
        # Get holidays data from NSE
        holidays_data = holiday_master('trading')
        
        if not holidays_data or 'CM' not in holidays_data:
            print("No CM holidays data received from nsepython")
            return pd.DataFrame(columns=["date", "day", "name"])
        
        # Get Cash Market holidays
        cm_holidays = holidays_data['CM']
        
        if not cm_holidays:
            print("No CM holidays found")
            return pd.DataFrame(columns=["date", "day", "name"])
        
        # Convert to DataFrame
        df = pd.DataFrame(cm_holidays)
        
        # Ensure we have the required columns
        if 'tradingDate' not in df.columns or 'description' not in df.columns or 'weekDay' not in df.columns:
            print(f"Unexpected data structure. Available columns: {list(df.columns)}")
            return pd.DataFrame(columns=["date", "day", "name"])
        
        # Parse and format the data
        df['date'] = pd.to_datetime(df['tradingDate'], format='%d-%b-%Y')
        df['day'] = df['weekDay']
        df['name'] = df['description']
        
        # Select only required columns and filter for 2025
        result_df = df[df['date'].dt.year == 2025][['date', 'day', 'name']].copy()
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        print(f"Successfully fetched {len(result_df)} holidays for 2025")
        return result_df
        
    except ImportError:
        print("nsepython not installed. Please install it with: pip install nsepython")
        return pd.DataFrame(columns=["date", "day", "name"])
    except Exception as e:
        print(f"Error fetching NSE holidays for 2025: {e}")
        return pd.DataFrame(columns=["date", "day", "name"])


def save_holidays_to_db(df: pd.DataFrame) -> int:
    """
    Save holidays to PostgreSQL database.
    
    Args:
        df: DataFrame with columns: date, day, name
        
    Returns:
        Number of holidays saved
    """
    if df.empty:
        return 0

    try:
        with get_conn() as conn:
            for _, row in df.iterrows():
                conn.execute(
                    text(
                        f"""
                        INSERT INTO {HOLIDAYS_TABLE} (date, day, name)
                        VALUES (:date, :day, :name)
                        ON CONFLICT (date)
                        DO UPDATE SET 
                            day = EXCLUDED.day,
                            name = EXCLUDED.name
                        """
                    ),
                    {
                        "date": row["date"].date(),
                        "day": row["day"],
                        "name": row["name"],
                    },
                )
            conn.commit()
        print(f"Successfully saved {len(df)} holidays to database")
        return len(df)
    except Exception as e:
        print(f"Error saving holidays to database: {e}")
        return 0


def get_holidays_from_db(year: int = None) -> pd.DataFrame:
    """
    Get holidays from database for a specific year.
    
    Args:
        year: Year to filter by. If None, returns all holidays.
        
    Returns:
        DataFrame with columns: date, day, name
    """
    try:
        with get_conn() as conn:
            if year:
                result = conn.execute(
                    text(f"""
                        SELECT date, day, name
                        FROM {HOLIDAYS_TABLE}
                        WHERE EXTRACT(YEAR FROM date) = :year
                        ORDER BY date
                    """),
                    {"year": year}
                )
            else:
                result = conn.execute(
                    text(f"""
                        SELECT date, day, name
                        FROM {HOLIDAYS_TABLE}
                        ORDER BY date
                    """)
                )
            
            rows = result.fetchall()
            
            if not rows:
                return pd.DataFrame(columns=["date", "day", "name"])
            
            df = pd.DataFrame(rows, columns=["date", "day", "name"])
            return df
    
    except Exception as e:
        print(f"Error fetching holidays from database: {e}")
        return pd.DataFrame(columns=["date", "day", "name"])


def get_holidays_for_year(year: int) -> pd.DataFrame:
    """
    Get holidays for a specific year.
    For current year and future years, fetches from NSE and saves to DB.
    For historical years, returns from DB only.
    
    Args:
        year: Year to get holidays for
        
    Returns:
        DataFrame with columns: date, day, name
    """
    try:
        from datetime import datetime
        current_year = datetime.now().year
        
        # First try to get from database
        df = get_holidays_from_db(year)
        
        # If no data found and it's current year or future, fetch from NSE
        if df.empty and year >= current_year:
            print(f"No holidays found in database for {year}, fetching from NSE...")
            df = fetch_nse_holidays_for_year(year)
            if not df.empty:
                save_holidays_to_db(df)
        
        return df
        
    except Exception as e:
        print(f"Error getting holidays for year {year}: {e}")
        return pd.DataFrame(columns=["date", "day", "name"])


def fetch_nse_holidays_for_year(year: int) -> pd.DataFrame:
    """
    Fetch NSE holidays for any year using nsepython.
    
    Returns:
        DataFrame with columns: date, day, name
    """
    try:
        print(f"Fetching NSE holidays for {year} using nsepython")
        
        holidays_data = holiday_master('trading')
        
        if not holidays_data or 'CM' not in holidays_data:
            print("No CM holidays data received from nsepython")
            return pd.DataFrame(columns=["date", "day", "name"])
        
        cm_holidays = holidays_data['CM']
        
        if not cm_holidays:
            print("No CM holidays found")
            return pd.DataFrame(columns=["date", "day", "name"])
        
        df = pd.DataFrame(cm_holidays)
        
        if 'tradingDate' not in df.columns or 'description' not in df.columns or 'weekDay' not in df.columns:
            print(f"Unexpected data structure. Available columns: {list(df.columns)}")
            return pd.DataFrame(columns=["date", "day", "name"])
        
        df['date'] = pd.to_datetime(df['tradingDate'], format='%d-%b-%Y')
        df['day'] = df['weekDay']
        df['name'] = df['description']
        
        result_df = df[df['date'].dt.year == year][['date', 'day', 'name']].copy()
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        print(f"Successfully fetched {len(result_df)} holidays for {year}")
        return result_df
        
    except ImportError:
        print("nsepython not installed. Please install it with: pip install nsepython")
        return pd.DataFrame(columns=["date", "day", "name"])
    except Exception as e:
        print(f"Error fetching NSE holidays for {year}: {e}")
        return pd.DataFrame(columns=["date", "day", "name"])


def load_holidays_from_csv() -> pd.DataFrame:
    """
    Load holidays from the CSV data provided by user (2011-2025).
    
    Returns:
        DataFrame with columns: date, day, name
    """
    try:
        # CSV data provided by user
        csv_data = """Year,Date,Day,Holiday
2011,2011-01-26,Wednesday,Republic Day
2011,2011-03-02,Wednesday,Mahashivratri
2011,2011-04-12,Tuesday,Ram Navmi
2011,2011-04-14,Thursday,Dr. Babasaheb Ambedkar Jayanti
2011,2011-04-22,Friday,Good Friday
2011,2011-08-15,Monday,Independence Day
2011,2011-08-31,Wednesday,Ramzan Id
2011,2011-09-01,Thursday,Shri Ganesh Chaturthi
2011,2011-10-06,Thursday,Dussehra
2011,2011-10-26,Wednesday,Diwali (Laxmi Pujan)
2011,2011-10-27,Thursday,Diwali Balipratipada
2011,2011-11-07,Monday,Bakri Id
2011,2011-11-10,Thursday,Gurunanak Jayanti
2011,2011-12-06,Tuesday,Muharram
2012,2012-01-26,Thursday,Republic Day
2012,2012-02-20,Monday,Mahashivratri
2012,2012-03-08,Thursday,Holi
2012,2012-04-05,Thursday,Mahavir Jayanti
2012,2012-04-06,Friday,Good Friday
2012,2012-05-01,Tuesday,Maharashtra Day
2012,2012-08-15,Wednesday,Independence Day
2012,2012-08-20,Monday,Ramzan Id
2012,2012-09-19,Wednesday,Ganesh Chaturthi
2012,2012-10-02,Tuesday,Mahatma Gandhi Jayanti
2012,2012-10-24,Wednesday,Dussehra (Vijaya Dashami)
2012,2012-10-26,Friday,Bakri Id
2012,2012-11-13,Tuesday,Diwali (Laxmi Pujan)
2012,2012-11-14,Wednesday,Diwali Balipratipada
2012,2012-11-28,Wednesday,Gurunanak Jayanti
2012,2012-12-25,Tuesday,Christmas
2013,2013-01-25,Friday,Id-E-Milad
2013,2013-03-27,Wednesday,Holi
2013,2013-03-29,Friday,Good Friday
2013,2013-04-24,Wednesday,Mahavir Jayanti
2013,2013-05-01,Wednesday,Maharashtra Day
2013,2013-08-09,Friday,Ramzan Id
2013,2013-08-15,Thursday,Independence Day
2013,2013-08-28,Wednesday,Krishna Janmashtami
2013,2013-09-09,Monday,Ganesh Chaturthi
2013,2013-10-02,Wednesday,Mahatma Gandhi Jayanti
2013,2013-10-16,Wednesday,Bakri Id
2013,2013-11-14,Thursday,Muharram
2013,2013-12-25,Wednesday,Christmas
2014,2014-02-27,Thursday,Mahashivratri
2014,2014-03-17,Monday,Holi
2014,2014-04-08,Tuesday,Ram Navami
2014,2014-04-14,Monday,Dr. Baba Saheb Ambedkar Jayanti
2014,2014-04-18,Friday,Good Friday
2014,2014-05-01,Thursday,May Day
2014,2014-07-29,Tuesday,Ramzan Id
2014,2014-08-15,Friday,Independence Day
2014,2014-08-29,Friday,Ganesh Chaturthi
2014,2014-10-02,Thursday,Mahatma Gandhi Jayanti
2014,2014-10-03,Friday,Dussehra
2014,2014-10-06,Monday,Bakri Id
2014,2014-10-23,Thursday,Diwali (Laxmi Pujan)
2014,2014-10-24,Friday,Diwali Balipratipada
2014,2014-11-04,Tuesday,Muharram
2014,2014-11-06,Thursday,Gurunanak Jayanti
2014,2014-12-25,Thursday,Christmas
2015,2015-01-26,Monday,Republic Day
2015,2015-02-17,Tuesday,Mahashivratri
2015,2015-02-19,Thursday,Chhatrapati Shivaji Maharaj Jayanti
2015,2015-03-06,Friday,Holi
2015,2015-04-01,Wednesday,Annual Closing of Banks
2015,2015-04-02,Thursday,Mahavir Jayanti
2015,2015-04-03,Friday,Good Friday
2015,2015-04-14,Tuesday,Dr. Baba Saheb Ambedkar Jayanti
2015,2015-05-01,Friday,Maharashtra Day
2015,2015-05-04,Monday,Buddha Purnima
2015,2015-08-18,Tuesday,Parsi New Year
2015,2015-09-17,Thursday,Ganesh Chaturthi
2015,2015-09-25,Friday,Bakri Id
2015,2015-10-02,Friday,Mahatma Gandhi Jayanti
2015,2015-10-22,Thursday,Dussehra
2015,2015-11-11,Wednesday,Diwali (Laxmi Pujan)
2015,2015-11-12,Thursday,Diwali Balipratipada
2015,2015-11-25,Wednesday,Gurunanak Jayanti
2015,2015-12-24,Thursday,Id-E-Milad
2015,2015-12-25,Friday,Christmas
2016,2016-01-26,Tuesday,Republic Day
2016,2016-03-07,Monday,Mahashivratri
2016,2016-03-24,Thursday,Holi
2016,2016-03-25,Friday,Good Friday
2016,2016-04-14,Thursday,Dr. Baba Saheb Ambedkar Jayanti
2016,2016-04-15,Friday,Ram Navami
2016,2016-04-19,Tuesday,Mahavir Jayanti
2016,2016-07-06,Wednesday,Id-Ul-Fitr (Ramzan Id)
2016,2016-08-15,Monday,Independence Day
2016,2016-09-05,Monday,Ganesh Chaturthi
2016,2016-09-13,Tuesday,Bakri Id
2016,2016-10-11,Tuesday,Dussehra
2016,2016-10-12,Wednesday,Muharram
2016,2016-10-31,Monday,Diwali
2016,2016-11-14,Monday,Gurunanak Jayanti
2017,2017-01-26,Thursday,Republic Day
2017,2017-02-24,Friday,Mahashivratri
2017,2017-03-13,Monday,Holi
2017,2017-04-04,Tuesday,Ram Navami
2017,2017-04-14,Friday,Dr. Baba Saheb Ambedkar Jayanti
2017,2017-04-19,Wednesday,Good Friday
2017,2017-05-01,Monday,Maharashtra Day
2017,2017-06-26,Monday,Id-Ul-Fitr (Ramzan Id)
2017,2017-08-15,Tuesday,Independence Day
2017,2017-08-25,Friday,Ganesh Chaturthi
2017,2017-10-02,Monday,Mahatma Gandhi Jayanti
2017,2017-10-19,Thursday,Diwali (Laxmi Pujan)
2017,2017-10-20,Friday,Diwali Balipratipada
2017,2017-12-25,Monday,Christmas
2018,2018-01-26,Friday,Republic Day
2018,2018-02-13,Tuesday,Mahashivratri
2018,2018-03-02,Friday,Holi
2018,2018-03-29,Thursday,Mahavir Jayanti
2018,2018-03-30,Friday,Good Friday
2018,2018-05-01,Tuesday,Maharashtra Day
2018,2018-08-15,Wednesday,Independence Day
2018,2018-08-22,Wednesday,Bakri Id
2018,2018-09-13,Thursday,Ganesh Chaturthi
2018,2018-09-20,Thursday,Muharram
2018,2018-10-02,Tuesday,Mahatma Gandhi Jayanti
2018,2018-10-18,Thursday,Dussehra
2018,2018-11-07,Wednesday,Diwali (Laxmi Pujan)
2018,2018-11-08,Thursday,Diwali Balipratipada
2018,2018-11-23,Friday,Gurunanak Jayanti
2018,2018-12-25,Tuesday,Christmas
2019,2019-03-04,Monday,Mahashivratri
2019,2019-03-21,Thursday,Holi
2019,2019-04-17,Wednesday,Mahavir Jayanti
2019,2019-04-19,Friday,Good Friday
2019,2019-04-29,Monday,General Elections (Lok Sabha)
2019,2019-05-01,Wednesday,Maharashtra Day
2019,2019-06-05,Wednesday,Id-Ul-Fitr (Ramzan Id)
2019,2019-08-12,Monday,Bakri Id
2019,2019-08-15,Thursday,Independence Day
2019,2019-09-02,Monday,Ganesh Chaturthi
2019,2019-09-10,Tuesday,Muharram
2019,2019-10-02,Wednesday,Mahatma Gandhi Jayanti
2019,2019-10-08,Tuesday,Dussehra
2019,2019-10-21,Monday,Maharashtra Assembly Election
2019,2019-10-28,Monday,Diwali Balipratipada
2019,2019-11-12,Tuesday,Gurunanak Jayanti
2019,2019-12-25,Wednesday,Christmas
2020,2020-02-21,Friday,Mahashivratri
2020,2020-03-10,Tuesday,Holi
2020,2020-03-29,Sunday,Holi
2020,2020-04-02,Thursday,Ram Navami
2020,2020-04-06,Monday,Mahavir Jayanti
2020,2020-04-10,Friday,Good Friday
2020,2020-04-14,Tuesday,Dr. Baba Saheb Ambedkar Jayanti
2020,2020-05-01,Friday,Maharashtra Day
2020,2020-05-25,Monday,Id-Ul-Fitr (Ramzan Id)
2020,2020-10-02,Friday,Mahatma Gandhi Jayanti
2020,2020-11-16,Monday,Diwali Balipratipada
2020,2020-11-30,Monday,Gurunanak Jayanti
2020,2020-12-25,Friday,Christmas
2021,2021-01-26,Tuesday,Republic Day
2021,2021-03-11,Thursday,Mahashivratri
2021,2021-03-29,Monday,Holi
2021,2021-04-02,Friday,Good Friday
2021,2021-04-14,Wednesday,Dr. Baba Saheb Ambedkar Jayanti
2021,2021-04-21,Wednesday,Ram Navami
2021,2021-05-13,Thursday,Id-Ul-Fitr (Ramzan Id)
2021,2021-07-21,Wednesday,Bakri Id
2021,2021-08-19,Thursday,Muharram
2021,2021-09-10,Friday,Ganesh Chaturthi
2021,2021-10-15,Friday,Dussehra
2021,2021-11-04,Thursday,Diwali (Laxmi Pujan)
2021,2021-11-05,Friday,Diwali Balipratipada
2021,2021-11-19,Friday,Gurunanak Jayanti
2022,2022-01-26,Wednesday,Republic Day
2022,2022-03-01,Tuesday,Mahashivratri
2022,2022-03-18,Friday,Holi
2022,2022-04-14,Thursday,Dr. Baba Saheb Ambedkar Jayanti; Mahavir Jayanti
2022,2022-04-15,Friday,Good Friday
2022,2022-05-03,Tuesday,Id-Ul-Fitr (Ramzan Id)
2022,2022-08-09,Tuesday,Muharram
2022,2022-08-15,Monday,Independence Day
2022,2022-08-31,Wednesday,Ganesh Chaturthi
2022,2022-10-05,Wednesday,Dussehra
2022,2022-10-24,Monday,Diwali (Laxmi Pujan)
2022,2022-10-26,Wednesday,Diwali Balipratipada
2022,2022-11-08,Tuesday,Gurunanak Jayanti
2023,2023-01-26,Thursday,Republic Day
2023,2023-03-07,Tuesday,Holi
2023,2023-03-30,Thursday,Ram Navami
2023,2023-04-04,Tuesday,Mahavir Jayanti
2023,2023-04-07,Friday,Good Friday
2023,2023-04-14,Friday,Dr. Baba Saheb Ambedkar Jayanti
2023,2023-05-01,Monday,Maharashtra Day
2023,2023-06-29,Thursday,Bakri Id
2023,2023-08-15,Tuesday,Independence Day
2023,2023-09-19,Tuesday,Ganesh Chaturthi
2023,2023-10-02,Monday,Mahatma Gandhi Jayanti
2023,2023-10-24,Tuesday,Dussehra
2023,2023-11-14,Tuesday,Diwali Balipratipada
2023,2023-11-27,Monday,Gurunanak Jayanti
2023,2023-12-25,Monday,Christmas
2024,2024-01-22,Monday,Special Holiday
2024,2024-01-26,Friday,Republic Day
2024,2024-03-08,Friday,Mahashivratri
2024,2024-03-25,Monday,Holi
2024,2024-03-29,Friday,Good Friday
2024,2024-04-11,Thursday,Id-Ul-Fitr (Ramadan Eid)
2024,2024-04-17,Wednesday,Shri Ram Navmi
2024,2024-05-01,Wednesday,Maharashtra Day
2024,2024-05-20,Monday,General Parliamentary Elections
2024,2024-06-17,Monday,Bakri Id
2024,2024-07-17,Wednesday,Moharram
2024,2024-08-15,Thursday,Independence Day; Parsi New Year
2024,2024-10-02,Wednesday,Mahatma Gandhi Jayanti
2024,2024-11-01,Friday,Diwali (Laxmi Pujan)
2024,2024-11-15,Friday,Gurunanak Jayanti
2024,2024-12-25,Wednesday,Christmas"""
        
        print("Loading holidays from provided CSV data...")
        
        # Read the CSV data
        from io import StringIO
        df = pd.read_csv(StringIO(csv_data))
        
        if df.empty:
            print("CSV data is empty")
            return pd.DataFrame(columns=["date", "day", "name"])
        
        print(f"CSV loaded with {len(df)} rows")
        print(f"CSV columns: {list(df.columns)}")
        
        # Parse the date column
        df['parsed_date'] = pd.to_datetime(df['Date'])
        
        # Filter out invalid dates
        df = df.dropna(subset=['parsed_date'])
        
        # Create the result DataFrame
        result_df = pd.DataFrame({
            'date': df['parsed_date'],
            'day': df['Day'],
            'name': df['Holiday']
        })
        
        # Sort by date
        result_df = result_df.sort_values('date').reset_index(drop=True)
        
        print(f"Successfully parsed {len(result_df)} holidays from CSV")
        return result_df
        
    except Exception as e:
        print(f"Error loading holidays from CSV: {e}")
        return pd.DataFrame(columns=["date", "day", "name"])


def load_all_historical_holidays() -> dict:
    """
    Load all historical holidays from CSV file into database.
    
    Returns:
        Dictionary with load status and count
    """
    try:
        print("Loading all historical holidays from CSV...")
        df = load_holidays_from_csv()
        
        if df.empty:
            return {
                "success": False,
                "message": "No holidays data found in CSV file",
                "count": 0
            }
        
        saved_count = save_holidays_to_db(df)
        
        return {
            "success": True,
            "message": f"Successfully loaded {saved_count} historical holidays from CSV",
            "count": saved_count
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error loading historical holidays: {str(e)}",
            "count": 0
        }


def refresh_holidays_2025() -> dict:
    """
    Refresh holidays for 2025 by fetching from NSE and updating database.
    
    Returns:
        Dictionary with refresh status and count
    """
    try:
        print("Refreshing holidays for 2025...")
        df = fetch_nse_holidays_2025()
        
        if df.empty:
            return {
                "success": False,
                "message": "No holidays data received from NSE",
                "count": 0
            }
        
        saved_count = save_holidays_to_db(df)
        
        return {
            "success": True,
            "message": f"Successfully refreshed {saved_count} holidays for 2025",
            "count": saved_count
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"Error refreshing holidays: {str(e)}",
            "count": 0
        }
