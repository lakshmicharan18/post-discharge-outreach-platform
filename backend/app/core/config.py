from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    environment: Literal["development", "test", "production"] = "development"
    enable_dev_auth: bool = False

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg://")
        if self.environment == "production" and self.enable_dev_auth:
            raise ValueError("Development authentication cannot be enabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
