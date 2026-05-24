from collections.abc import Mapping
from pathlib import Path


def sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return database_url


def alembic_database_url(
    *,
    environ: Mapping[str, str],
    dotenv_path: Path = Path(".env"),
) -> str:
    database_url = environ.get("DATABASE_URL") or _database_url_from_dotenv(dotenv_path)
    return sync_database_url(database_url or "sqlite:///./washbot_dev.db")


def _database_url_from_dotenv(dotenv_path: Path) -> str | None:
    if not dotenv_path.exists():
        return None

    for line in dotenv_path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "DATABASE_URL":
            return value.strip().strip("\"'")
    return None
