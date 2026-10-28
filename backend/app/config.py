from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "TracePulse"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # Database Settings
    # Default is MySQL async, can be overridden by environment variable or set to SQLite for local development
    DATABASE_URL: str = "mysql+asyncmy://root:root@127.0.0.1:3306/tracepulse"
    SQLITE_FALLBACK_URL: str = "sqlite+aiosqlite:///./tracepulse.db"
    
    # Internal Probe Ingestion Token / Auth (optional)
    INTERNAL_INGEST_KEY: str = "tp-internal-probe-secret"
    
    # Probe Daemon Defaults
    DEFAULT_CHECK_INTERVAL_SEC: int = 10
    DEFAULT_TIMEOUT_MS: int = 5000
    
    # Webhook Defaults
    ALERT_DISPATCH_TIMEOUT_SEC: float = 3.0
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
