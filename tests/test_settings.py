import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_settings_load_defaults_with_required_values() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
    )

    assert settings.app_env == "local"
    assert str(settings.database_url).startswith("postgresql+asyncpg://")
    assert settings.telegram_bot_token.get_secret_value() == "token"
    assert settings.default_reminder_before_minutes == 60


def test_settings_load_default_customer_booking_ids() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
    )

    assert settings.default_car_wash_id == 1
    assert settings.default_branch_id == 1


def test_settings_parse_admin_telegram_ids_from_comma_string() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
        admin_telegram_ids="1001, 1002",
    )

    assert settings.admin_telegram_ids == (1001, 1002)


def test_settings_default_admin_telegram_ids_is_empty() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
    )

    assert settings.admin_telegram_ids == ()


def test_settings_reject_invalid_admin_telegram_ids() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
            telegram_bot_token="token",
            admin_telegram_ids="1001,not-a-number",
        )


def test_settings_parse_admin_telegram_ids_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/washbot",
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "1001,1002")

    settings = Settings(_env_file=None)

    assert settings.admin_telegram_ids == (1001, 1002)
