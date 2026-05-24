from pathlib import Path

from app.db.url import alembic_database_url, sync_database_url


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


def test_alembic_database_url_prefers_environment() -> None:
    assert (
        alembic_database_url(
            environ={"DATABASE_URL": "sqlite+aiosqlite:///from-env.db"},
            dotenv_path=Path("missing.env"),
        )
        == "sqlite:///from-env.db"
    )


def test_alembic_database_url_reads_utf8_sig_dotenv(tmp_path: Path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\ufeffAPP_ENV=local\nDATABASE_URL=sqlite+aiosqlite:///from-dotenv.db\n",
        encoding="utf-8",
    )

    assert alembic_database_url(environ={}, dotenv_path=dotenv_path) == "sqlite:///from-dotenv.db"


def test_alembic_database_url_uses_dev_fallback_without_env_or_dotenv() -> None:
    assert alembic_database_url(environ={}, dotenv_path=Path("missing.env")) == (
        "sqlite:///./washbot_dev.db"
    )
