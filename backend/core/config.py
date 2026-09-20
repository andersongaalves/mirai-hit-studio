from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    API_NAME: str
    API_VERSION: str

    DEBUG: bool

    HOST: str
    PORT: int

    LOG_LEVEL: str

    SECRET_KEY: str
    ALGORITHM: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    DATABASE_URL: str

    ALLOWED_ORIGINS: str

    BACKUP_FOLDER: str
    BACKUP_KEEP_DAYS: int

    RESEND_API_KEY: str
    EMAIL_FROM: str
    ADMIN_EMAIL: str
    PUBLIC_API_URL: str = "http://localhost:8000"

    MERCADO_PAGO_ACCESS_TOKEN: str | None = None
    MERCADO_PAGO_PUBLIC_KEY: str | None = None
    MERCADO_PAGO_WEBHOOK_SECRET: str | None = None
    MERCADO_PAGO_TIMEOUT_SECONDS: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
