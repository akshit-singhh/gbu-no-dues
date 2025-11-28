from pydantic_settings import BaseSettings

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

    # --- EMAIL SETTINGS (ADD THESE) ---
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 2525  # Default to Mailtrap port
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: str = "no-reply@gbu.ac.in"
    EMAILS_FROM_NAME: str = "GBU No Dues"
    FRONTEND_URL: str = "http://localhost:5173" # For login link

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()