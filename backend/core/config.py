from typing import Literal

from pydantic import Field, SecretStr
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

    RESEND_API_KEY: str = ""
    EMAIL_FROM: str
    ADMIN_EMAIL: str
    PUBLIC_API_URL: str = "http://localhost:8000"
    PUBLIC_FRONTEND_URL: str = "http://localhost:4173"
    AI_ENABLED: bool = False
    AI_PROVIDER: str = ""
    AI_BASE_URL: str = ""
    AI_MODEL: str = ""
    AI_API_KEY: SecretStr = SecretStr("")
    AI_TIMEOUT_SECONDS: float = Field(default=8, ge=1, le=10)
    AI_MAX_OUTPUT_TOKENS: int = Field(default=1200, ge=128, le=4096)
    AI_SESSION_HOURS: int = Field(default=24, ge=1, le=168)
    AI_EMAIL_ENABLED: bool = False
    AI_EMAIL_FROM: str = ""
    AI_EMAIL_INBOUND_ADDRESS: str = ""
    AI_EMAIL_MAX_BODY_CHARS: int = Field(default=8000, ge=1000, le=20000)
    RESEND_WEBHOOK_SECRET: SecretStr = SecretStr("")

    MERCADO_PAGO_ACCESS_TOKEN: str | None = None
    MERCADO_PAGO_PUBLIC_KEY: str | None = None
    MERCADO_PAGO_WEBHOOK_SECRET: str | None = None
    MERCADO_PAGO_TIMEOUT_SECONDS: float = 10.0
    MERCADO_PAGO_3DS_VALIDATION: Literal["never", "on_fraud_risk"] = "on_fraud_risk"
    COMMERCIAL_PIPELINE_V2_ENABLED: bool = False

    # Storage core. Existing product flows remain on their legacy factories until
    # the corresponding migration phase explicitly wires them to the registry.
    PUBLIC_IMAGE_STORAGE_BACKEND: str = "cloudinary"
    PORTFOLIO_AUDIO_STORAGE_BACKEND: str = "supabase"
    PRODUCTION_TEMP_STORAGE_BACKEND: str = "r2"
    PRODUCTION_FINAL_STORAGE_BACKEND: str = "r2"
    PROPOSAL_DOCUMENT_STORAGE_BACKEND: str = "legacy"
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: SecretStr = SecretStr("")
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    R2_TEMP_BUCKET: str = ""
    R2_FINAL_BUCKET: str = ""
    R2_ENDPOINT: str = ""
    R2_REGION: str = "auto"
    R2_PRESIGN_MAX_SECONDS: int = Field(default=900, ge=1, le=3600)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
