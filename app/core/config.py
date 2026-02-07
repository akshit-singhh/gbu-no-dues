from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Set, Optional
from pydantic import computed_field

class Settings(BaseSettings):
    # ------------------------------------------------------------
    # DATABASE CONFIGURATION
    # ------------------------------------------------------------
    DATABASE_URL: str
    DB_SSL_VERIFY: bool = True
    db_ca_cert_path: Optional[str] = None

    # ------------------------------------------------------------
    # CORE APP SETTINGS
    # ------------------------------------------------------------
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ENV: str = "prod"  # Defaults to prod, must be overridden to "dev" locally

    @computed_field
    @property
    def DEBUG(self) -> bool:
        return self.ENV.lower() == "prod"

    # ------------------------------------------------------------
    # FIRST ADMIN CONFIGURATION
    # ------------------------------------------------------------
    ADMIN_EMAIL: Optional[str] = None
    ADMIN_PASSWORD: Optional[str] = None
    ADMIN_NAME: Optional[str] = "Admin"
    
    # ------------------------------------------------------------
    # BUSINESS LOGIC CONFIGURATION
    # ------------------------------------------------------------
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
    # REMOVED DEFAULTS: These MUST be provided in Vercel/Env now
    FRONTEND_URL: str  
    FRONTEND_URLS: str 
    FRONTEND_REGEX: Optional[str] = None

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
        extra="ignore",
        case_sensitive=False
    )

settings = Settings()
