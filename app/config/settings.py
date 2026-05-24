from typing import Annotated, Any

from pydantic import AnyUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "local"
    database_url: AnyUrl
    telegram_bot_token: SecretStr
    default_reminder_before_minutes: int = Field(default=60, ge=0, le=1440)
    default_car_wash_id: int = Field(default=1, ge=1)
    default_branch_id: int = Field(default=1, ge=1)
    admin_telegram_ids: Annotated[tuple[int, ...], NoDecode] = Field(default_factory=tuple)

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_telegram_ids(cls, value: Any) -> tuple[int, ...]:
        if value is None or value == "":
            return ()
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return tuple(int(part) for part in parts)
        if isinstance(value, list | tuple | set):
            return tuple(int(part) for part in value)
        raise TypeError("admin_telegram_ids must be a comma-separated string or iterable.")
