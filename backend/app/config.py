import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    WB_API_TOKEN: str = os.getenv("WB_API_TOKEN", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://bidder:WbBidder2026Secure@localhost:5432/wb_bidder")
    DATABASE_URL_SYNC: str = os.getenv("DATABASE_URL_SYNC", "postgresql+psycopg2://bidder:WbBidder2026Secure@localhost:5432/wb_bidder")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    APP_TIMEZONE: str = os.getenv("APP_TIMEZONE", "Europe/Moscow")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
