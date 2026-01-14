# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set

class Settings(BaseSettings):
    DATABASE_URL: str

    # If DEV and you hit SSL cert issues on Windows, set DB_SSL_VERIFY=false in .env
    DB_SSL_VERIFY: bool = True

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    SUPER_ADMIN_EMAIL: str | None = None
    SUPER_ADMIN_PASSWORD: str | None = None
    SUPER_ADMIN_NAME: str | None = "Super Admin"
    db_ca_cert_path: str | None = None
    ENV: str = "dev"  # "dev" or "prod"

    # --- LOGIC CONFIGURATION ---
    # Codes of Schools that do NOT require Lab Clearance.
    # Using a Set for fast lookup (O(1)).
    SCHOOLS_WITHOUT_LABS: Set[str] = {"SOL", "HSS"} 

    # --- EMAIL SETTINGS ---
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 2525
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str = "no-reply@gbu.ac.in"
    EMAILS_FROM_NAME: str = "GBU No Dues"
    FRONTEND_URL: str = "http://localhost:5173"

    
    # Using | None = None allows it to start even if keys are missing initially
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None

    # This handles loading from .env and ignoring extra variables if any
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" 
    )

settings = Settings()