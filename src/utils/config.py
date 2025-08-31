from dataclasses import dataclass
import os
from dotenv import load_dotenv


# Ensure .env is loaded before reading environment variables
load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Automated Trading Platform")
    environment: str = os.getenv("ENVIRONMENT", "development")

    breeze_api_key: str | None = os.getenv("BREEZE_API_KEY")
    breeze_api_secret: str | None = os.getenv("BREEZE_API_SECRET")
    breeze_session_token: str | None = os.getenv("BREEZE_SESSION_TOKEN")

    # PostgreSQL DSN (e.g., postgresql+psycopg://user:pass@localhost:5432/dbname)
    postgres_dsn: str | None = os.getenv("POSTGRES_DSN")

    # Holidays CSV path (preferred source). Default points to repo CSV under src/
    holidays_csv_path: str = os.getenv("HOLIDAYS_CSV_PATH", "src/HolidaycalenderData.csv")

    # Market holidays (optional): comma-separated YYYY-MM-DD list
    market_holidays_raw: str | None = os.getenv("MARKET_HOLIDAYS")

    @property
    def market_holidays(self) -> set[str]:
        raw = (self.market_holidays_raw or "").strip()
        if not raw:
            return set()
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        valid = set()
        for p in parts:
            # basic validation YYYY-MM-DD
            if len(p) == 10 and p[4] == '-' and p[7] == '-':
                valid.add(p)
        return valid


settings = Settings()


