from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv


# Ensure .env is loaded before reading environment variables
# Look for .env file in the backend directory
backend_dir = Path(__file__).parent.parent
env_path = backend_dir / ".env"
load_dotenv(env_path)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Automated Trading Platform")
    environment: str = os.getenv("ENVIRONMENT", "development")

    breeze_api_key: str | None = os.getenv("BREEZE_API_KEY")
    breeze_api_secret: str | None = os.getenv("BREEZE_API_SECRET")
    breeze_session_token: str | None = os.getenv("BREEZE_SESSION_TOKEN")

    # PostgreSQL DSN (e.g., postgresql+psycopg://user:pass@localhost:5432/dbname)
    postgres_dsn: str | None = os.getenv("POSTGRES_DSN")

    # Control whether to run instruments first-load automatically on login
    instruments_first_run_on_login: bool = os.getenv("INSTRUMENTS_FIRST_RUN_ON_LOGIN", "true").lower() in ("1", "true", "yes")


settings = Settings()


