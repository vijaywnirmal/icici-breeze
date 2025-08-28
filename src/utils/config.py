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


settings = Settings()


