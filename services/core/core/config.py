"""Core servis ayarları. Sahip: Damla."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    database_url: str = "postgresql+psycopg://parking:parking@localhost:5432/parking"
    redis_url: str = "redis://localhost:6379/0"
    core_port: int = 8001


settings = Settings()
