from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set, Optional
from pydantic import computed_field

class Settings(BaseSettings):
    # ------------------------------------------------------------
    # DATABASE CONFIGURATION
    # ------------------------------------------------------------
    DATABASE_URL: str
    # If DEV and you hit SSL cert issues on Windows, set DB_SSL_VERIFY=false in .env
    DB_SSL_VERIFY: bool = True
    db_ca_cert_path: Optional[str] = None

    # ------------------------------------------------------------
    # CORE APP SETTINGS
    # ------------------------------------------------------------
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENV: str = "dev"  # "dev" or "prod"

    @computed_field
    @property
    def DEBUG(self) -> bool:
        """Automatically sets DEBUG to True if ENV is 'dev'"""
        return self.ENV.lower() == "dev"

    # ------------------------------------------------------------
    # FIRST ADMIN CONFIGURATION
    # ------------------------------------------------------------
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_NAME: Optional[str] = "Admin"
    
    # ------------------------------------------------------------
    # BUSINESS LOGIC CONFIGURATION
    # ------------------------------------------------------------
    # Ensure these match the 'code' column in your 'schools' table exactly.
    SCHOOLS_WITHOUT_LABS: Set[str] = {"SOL", "SOHSS", "SOM"} 
    SCHOOLS_WITHOUT_LIBRARY: Set[str] = {""}

    # ------------------------------------------------------------
    # EMAIL (SMTP) SETTINGS
    # ------------------------------------------------------------
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 2525
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: str = "no-reply@gbu.ac.in"
    EMAILS_FROM_NAME: str = "GBU No Dues"

    # ------------------------------------------------------------
    # FRONTEND / CORS CONFIGURATION
    # ------------------------------------------------------------
    # 1. For Email Links (Single Base URL)
    FRONTEND_URL: str = "http://localhost:5173"

    # 2. For CORS Middleware (Comma-separated list)
    FRONTEND_URLS: str = "http://localhost:5173"

    # Regex for dynamic deployments (Vercel previews, DevTunnels, etc.)
    FRONTEND_REGEX: Optional[str] = ""

    # ------------------------------------------------------------
    # EXTERNAL SERVICES (SUPABASE / CLOUD)
    # ------------------------------------------------------------
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # ------------------------------------------------------------
    # SETTINGS CONFIG
    # ------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Prevents crashing if extra variables are in .env
        case_sensitive=False
    )

settings = Settings()