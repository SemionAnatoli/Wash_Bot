from app.db.url import sync_database_url


def test_sync_database_url_converts_async_postgres_driver() -> None:
    assert (
        sync_database_url("postgresql+asyncpg://user:pass@localhost:5432/washbot")
        == "postgresql://user:pass@localhost:5432/washbot"
    )


def test_sync_database_url_converts_async_sqlite_driver() -> None:
    assert (
        sync_database_url("sqlite+aiosqlite:///data/washbot.local.db")
        == "sqlite:///data/washbot.local.db"
    )


def test_sync_database_url_keeps_sync_url() -> None:
    assert sync_database_url("sqlite:///data/washbot.local.db") == (
        "sqlite:///data/washbot.local.db"
    )
