from pydantic import AnyUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "local"
    database_url: AnyUrl
    telegram_bot_token: SecretStr
    default_reminder_before_minutes: int = Field(default=60, ge=0, le=1440)
    default_car_wash_id: int = Field(default=1, ge=1)
    default_branch_id: int = Field(default=1, ge=1)
