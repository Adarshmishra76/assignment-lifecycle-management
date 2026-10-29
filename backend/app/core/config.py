from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Assignment Lifecycle Management"
    database_url: str = "sqlite:///./assignment_management.db"
    secret_key: str = "change-me-to-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    bootstrap_admin_email: str = "admin@demo.local"
    bootstrap_admin_password: str = "DemoPass123!"
    generator_seed: int = 20261022
    generator_mode: str = "starter"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
