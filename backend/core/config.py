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

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()