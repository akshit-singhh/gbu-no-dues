# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set

class Settings(BaseSettings):
    DATABASE_URL: str

    # If DEV and you hit SSL cert issues on Windows, set DB_SSL_VERIFY=false in .env
    DB_SSL_VERIFY: bool = True

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # These variables define the "First Admin" created on startup.
    # Note: Even though named "SUPER_ADMIN", this user will get the 'admin' role.
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    ADMIN_NAME: str | None = "Admin"
    
    db_ca_cert_path: str | None = None
    ENV: str = "dev"  # "dev" or "prod"

    # ------------------------------------------------------------
    # LOGIC CONFIGURATION
    # ------------------------------------------------------------
    # Schools that skip specific clearance steps
    SCHOOLS_WITHOUT_LABS: Set[str] = {"SOL", "HSS", "SOM"}
    SCHOOLS_WITHOUT_LIBRARY: Set[str] = {"VOC"}

    # ------------------------------------------------------------
    # EMAIL SETTINGS
    # ------------------------------------------------------------
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 2525
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str = "no-reply@gbu.ac.in"
    EMAILS_FROM_NAME: str = "GBU No Dues"

    # ------------------------------------------------------------
    # FRONTEND / CORS CONFIGURATION
    # ------------------------------------------------------------
    
    # 1. For Email Links (Single Base URL) - Fixes AttributeError
    FRONTEND_URL: str = "http://localhost:5173"

    # 2. For CORS Middleware (Comma-separated list)
    # Example: "https://myapp.vercel.app,http://localhost:5173"
    FRONTEND_URLS: str = "http://localhost:5173"

    # Regex for dynamic deployments (Vercel previews, Leapcell, DevTunnels)
    FRONTEND_REGEX: str = ""

    # ------------------------------------------------------------
    # SUPABASE
    # ------------------------------------------------------------
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None

    # ------------------------------------------------------------
    # SETTINGS CONFIG
    # ------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()