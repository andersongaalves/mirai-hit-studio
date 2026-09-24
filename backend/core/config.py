from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr


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
    PUBLIC_FRONTEND_URL: str = "http://localhost:4173"
    AI_ENABLED: bool = False
    AI_MODEL: str = ""
    AI_API_KEY: SecretStr = SecretStr("")
    AI_TIMEOUT_SECONDS: float = Field(default=8, ge=1, le=10)
    AI_SESSION_HOURS: int = Field(default=24, ge=1, le=168)

    MERCADO_PAGO_ACCESS_TOKEN: str | None = None
    MERCADO_PAGO_PUBLIC_KEY: str | None = None
    MERCADO_PAGO_WEBHOOK_SECRET: str | None = None
    MERCADO_PAGO_TIMEOUT_SECONDS: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
