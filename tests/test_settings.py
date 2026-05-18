from app.config.settings import Settings


def test_settings_load_defaults_with_required_values() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
    )

    assert settings.app_env == "local"
    assert str(settings.database_url).startswith("postgresql+asyncpg://")
    assert settings.telegram_bot_token.get_secret_value() == "token"
    assert settings.default_reminder_before_minutes == 60


def test_settings_load_default_customer_booking_ids() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
    )

    assert settings.default_car_wash_id == 1
    assert settings.default_branch_id == 1
