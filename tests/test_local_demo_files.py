from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_env_local_example_documents_sqlite_demo_config() -> None:
    text = (ROOT / ".env.local.example").read_text(encoding="utf-8")

    assert "DATABASE_URL=sqlite+aiosqlite:///data/washbot.local.db" in text
    assert "TELEGRAM_BOT_TOKEN=replace-me" in text
    assert "ADMIN_TELEGRAM_IDS=" in text
    assert "DEFAULT_CAR_WASH_ID=1" in text
    assert "DEFAULT_BRANCH_ID=1" in text


def test_gitignore_excludes_local_sqlite_data_directory() -> None:
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "data/" in text.splitlines()
    assert ".env" in text.splitlines()


def test_readme_documents_local_demo_runbook() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "python -m alembic upgrade head" in text
    assert "python -m scripts.seed_demo" in text
    assert "python -m app.bot.main" in text
    assert ".env.local.example" in text
    assert "TELEGRAM_BOT_TOKEN" in text
    assert "ADMIN_TELEGRAM_IDS" in text
    assert "sqlite+aiosqlite:///data/washbot.local.db" in text
