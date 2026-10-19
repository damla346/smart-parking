"""Gateway ayarları. Sahip: Berat."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    # USE_MOCK=true iken core yerine mock_core hedeflenir (YOL_HARITASI.md §6)
    use_mock: bool = True
    core_url: str = "http://localhost:8001"
    core_mock_url: str = "http://localhost:8101"
    redis_url: str = "redis://localhost:6379/0"
    gateway_port: int = 8000

    @property
    def effective_core_url(self) -> str:
        return self.core_mock_url if self.use_mock else self.core_url


settings = Settings()
