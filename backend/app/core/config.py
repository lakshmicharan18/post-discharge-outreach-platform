from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    environment: Literal["development", "test", "production"] = "development"
    jwt_secret: SecretStr
    jwt_access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    llm_provider: Literal["deterministic", "openai_compatible"] = "deterministic"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model: str = "deterministic"
    llm_timeout_seconds: int = Field(default=20, ge=1, le=120)
    llm_max_retries: int = Field(default=1, ge=0, le=3)

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if not self.database_url.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg://")
        if len(self.jwt_secret.get_secret_value().encode()) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 bytes")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
