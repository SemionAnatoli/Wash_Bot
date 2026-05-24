# WashBot Local Demo Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Telegram MVP runnable locally with a SQLite database, repeatable demo seed data, and a clear runbook.

**Architecture:** Keep runtime startup in `app/bot/main.py`, reusable demo seed logic in `app/demo_seed.py`, and thin command wrappers under `scripts/`. Add a small database URL helper so Alembic can run sync migrations against async runtime URLs such as `sqlite+aiosqlite:///data/washbot.local.db`.

**Tech Stack:** Python 3.12, aiogram 3, SQLAlchemy async ORM, Alembic, SQLite via aiosqlite, Pydantic Settings, pytest, Ruff, mypy.

---

## File Structure

Create or modify:

- `.env.local.example`: local SQLite example config.
- `.gitignore`: ignore local SQLite `data/` directory.
- `README.md`: local setup and manual Telegram test runbook.
- `app/db/url.py`: convert async DB URLs to sync URLs for Alembic.
- `migrations/env.py`: use `app.db.url.sync_database_url`.
- `app/demo_seed.py`: reusable idempotent demo seed logic.
- `scripts/__init__.py`: make `scripts` runnable as a module package.
- `scripts/seed_demo.py`: command wrapper for `python -m scripts.seed_demo`.
- `app/bot/main.py`: polling entrypoint and testable runtime builder.
- `tests/test_local_demo_files.py`: file and runbook checks.
- `tests/db/test_database_url.py`: database URL conversion checks.
- `tests/test_demo_seed.py`: demo seed behavior checks.
- `tests/test_seed_demo_script.py`: seed script wiring checks.
- `tests/bot/test_main.py`: bot runtime wiring checks.

## Task 1: Local Config And Alembic URL Helper

**Files:**
- Create: `app/db/url.py`
- Modify: `migrations/env.py`
- Create: `.env.local.example`
- Modify: `.gitignore`
- Test: `tests/db/test_database_url.py`
- Test: `tests/test_local_demo_files.py`

- [ ] **Step 1: Write failing tests for local files and URL conversion**

Create `tests/db/test_database_url.py`:

```python
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
```

Create `tests/test_local_demo_files.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/db/test_database_url.py tests/test_local_demo_files.py -q
```

Expected: FAIL because `app.db.url` and `.env.local.example` do not exist, and `.gitignore` does not ignore `data/`.

- [ ] **Step 3: Add database URL helper**

Create `app/db/url.py`:

```python
def sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return database_url
```

- [ ] **Step 4: Wire helper into Alembic**

Modify `migrations/env.py` imports:

```python
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.url import sync_database_url
```

Replace the current database URL conversion block with:

```python
config = context.config
database_url = sync_database_url(os.environ.get("DATABASE_URL", "sqlite:///./washbot_dev.db"))
config.set_main_option("sqlalchemy.url", database_url)
```

- [ ] **Step 5: Add local environment example and gitignore entry**

Create `.env.local.example`:

```env
APP_ENV=local
DATABASE_URL=sqlite+aiosqlite:///data/washbot.local.db
TELEGRAM_BOT_TOKEN=replace-me
DEFAULT_REMINDER_BEFORE_MINUTES=60
DEFAULT_CAR_WASH_ID=1
DEFAULT_BRANCH_ID=1
ADMIN_TELEGRAM_IDS=
```

Append to `.gitignore`:

```gitignore
data/
```

- [ ] **Step 6: Run focused tests and checks**

Run:

```bash
python -m pytest tests/db/test_database_url.py tests/test_local_demo_files.py -q
python -m ruff check app/db/url.py migrations/env.py tests/db/test_database_url.py tests/test_local_demo_files.py
python -m ruff format --check app/db/url.py migrations/env.py tests/db/test_database_url.py tests/test_local_demo_files.py
python -m mypy app/db/url.py
```

Expected: all commands pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add app/db/url.py migrations/env.py .env.local.example .gitignore tests/db/test_database_url.py tests/test_local_demo_files.py
git commit -m "feat: add local demo config"
```

## Task 2: Idempotent Demo Seed Logic

**Files:**
- Create: `app/demo_seed.py`
- Test: `tests/test_demo_seed.py`

- [ ] **Step 1: Write failing demo seed tests**

Create `tests/test_demo_seed.py`:

```python
from datetime import time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, CarWash, Service, WorkingHours
from app.demo_seed import seed_demo_data


async def count_rows(db_session: AsyncSession, model) -> int:
    return (
        await db_session.execute(select(func.count()).select_from(model))
    ).scalar_one()


async def test_seed_demo_data_creates_local_demo_setup(db_session: AsyncSession) -> None:
    result = await seed_demo_data(db_session, car_wash_id=1, branch_id=1)

    car_wash = await db_session.get(CarWash, result.car_wash_id)
    branch = await db_session.get(Branch, result.branch_id)
    services = (
        await db_session.execute(select(Service).order_by(Service.is_addon, Service.title))
    ).scalars().all()
    hours = (
        await db_session.execute(select(WorkingHours).order_by(WorkingHours.weekday))
    ).scalars().all()

    assert car_wash is not None
    assert car_wash.name == "Demo Wash"
    assert car_wash.confirmation_mode == "manual"
    assert car_wash.reminder_before_minutes == 60
    assert branch is not None
    assert branch.car_wash_id == car_wash.id
    assert branch.title == "Main"
    assert branch.address == "Demo street"
    assert branch.bay_count == 1
    assert result.main_service_count == 2
    assert result.addon_service_count == 3
    assert [(service.title, service.price, service.duration_minutes, service.is_addon) for service in services] == [
        ("Комплекс", Decimal("1500.00"), 90, False),
        ("Стандартная мойка", Decimal("900.00"), 60, False),
        ("Воск", Decimal("250.00"), 15, True),
        ("Уборка салона", Decimal("700.00"), 30, True),
        ("Чернение шин", Decimal("200.00"), 10, True),
    ]
    assert len(hours) == 7
    assert {working_hours.weekday for working_hours in hours} == set(range(7))
    assert all(working_hours.start_time == time(10) for working_hours in hours)
    assert all(working_hours.end_time == time(20) for working_hours in hours)


async def test_seed_demo_data_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_demo_data(db_session, car_wash_id=1, branch_id=1)
    second = await seed_demo_data(db_session, car_wash_id=1, branch_id=1)

    assert first == second
    assert await count_rows(db_session, CarWash) == 1
    assert await count_rows(db_session, Branch) == 1
    assert await count_rows(db_session, Service) == 5
    assert await count_rows(db_session, WorkingHours) == 7
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_demo_seed.py -q
```

Expected: FAIL because `app.demo_seed` does not exist.

- [ ] **Step 3: Add demo seed implementation**

Create `app/demo_seed.py`:

```python
from dataclasses import dataclass
from datetime import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, CarWash, Service, WorkingHours


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    car_wash_id: int
    branch_id: int
    main_service_count: int
    addon_service_count: int
    working_hours_count: int


DEMO_MAIN_SERVICES = (
    ("Стандартная мойка", "wash", Decimal("900.00"), 60),
    ("Комплекс", "wash", Decimal("1500.00"), 90),
)

DEMO_ADDON_SERVICES = (
    ("Воск", "addon", Decimal("250.00"), 15),
    ("Чернение шин", "addon", Decimal("200.00"), 10),
    ("Уборка салона", "addon", Decimal("700.00"), 30),
)


async def seed_demo_data(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
) -> DemoSeedResult:
    car_wash = await _ensure_car_wash(session, car_wash_id=car_wash_id)
    branch = await _ensure_branch(
        session,
        car_wash_id=car_wash.id,
        branch_id=branch_id,
    )
    await _ensure_working_hours(session, car_wash_id=car_wash.id, branch_id=branch.id)
    await _ensure_services(session, car_wash_id=car_wash.id)
    await session.commit()

    return DemoSeedResult(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        main_service_count=len(DEMO_MAIN_SERVICES),
        addon_service_count=len(DEMO_ADDON_SERVICES),
        working_hours_count=7,
    )


async def _ensure_car_wash(session: AsyncSession, *, car_wash_id: int) -> CarWash:
    car_wash = await session.get(CarWash, car_wash_id)
    if car_wash is None:
        car_wash = CarWash(id=car_wash_id, name="Demo Wash")
        session.add(car_wash)
        await session.flush()

    car_wash.name = "Demo Wash"
    car_wash.confirmation_mode = "manual"
    car_wash.reminder_before_minutes = 60
    return car_wash


async def _ensure_branch(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
) -> Branch:
    branch = await session.get(Branch, branch_id)
    if branch is None or branch.car_wash_id != car_wash_id:
        result = await session.execute(
            select(Branch).where(Branch.car_wash_id == car_wash_id, Branch.title == "Main")
        )
        branch = result.scalar_one_or_none()

    if branch is None:
        branch = Branch(
            id=branch_id,
            car_wash_id=car_wash_id,
            title="Main",
            address="Demo street",
            bay_count=1,
        )
        session.add(branch)
        await session.flush()

    branch.title = "Main"
    branch.address = "Demo street"
    branch.bay_count = 1
    return branch


async def _ensure_working_hours(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
) -> None:
    for weekday in range(7):
        result = await session.execute(
            select(WorkingHours).where(
                WorkingHours.car_wash_id == car_wash_id,
                WorkingHours.branch_id == branch_id,
                WorkingHours.weekday == weekday,
            )
        )
        working_hours = result.scalar_one_or_none()
        if working_hours is None:
            working_hours = WorkingHours(
                car_wash_id=car_wash_id,
                branch_id=branch_id,
                weekday=weekday,
                start_time=time(10),
                end_time=time(20),
            )
            session.add(working_hours)
        else:
            working_hours.start_time = time(10)
            working_hours.end_time = time(20)


async def _ensure_services(session: AsyncSession, *, car_wash_id: int) -> None:
    for title, category, price, duration_minutes in DEMO_MAIN_SERVICES:
        await _ensure_service(
            session,
            car_wash_id=car_wash_id,
            title=title,
            category=category,
            price=price,
            duration_minutes=duration_minutes,
            is_addon=False,
        )
    for title, category, price, duration_minutes in DEMO_ADDON_SERVICES:
        await _ensure_service(
            session,
            car_wash_id=car_wash_id,
            title=title,
            category=category,
            price=price,
            duration_minutes=duration_minutes,
            is_addon=True,
        )


async def _ensure_service(
    session: AsyncSession,
    *,
    car_wash_id: int,
    title: str,
    category: str,
    price: Decimal,
    duration_minutes: int,
    is_addon: bool,
) -> Service:
    result = await session.execute(
        select(Service).where(Service.car_wash_id == car_wash_id, Service.title == title)
    )
    service = result.scalar_one_or_none()
    if service is None:
        service = Service(
            car_wash_id=car_wash_id,
            title=title,
            category=category,
            price=price,
            duration_minutes=duration_minutes,
            is_addon=is_addon,
            is_active=True,
        )
        session.add(service)
    else:
        service.category = category
        service.price = price
        service.duration_minutes = duration_minutes
        service.is_addon = is_addon
        service.is_active = True
    return service
```

- [ ] **Step 4: Run seed tests and checks**

Run:

```bash
python -m pytest tests/test_demo_seed.py -q
python -m ruff check app/demo_seed.py tests/test_demo_seed.py
python -m ruff format --check app/demo_seed.py tests/test_demo_seed.py
python -m mypy app/demo_seed.py
```

Expected: all commands pass. If Ruff reports formatting, run `python -m ruff format app/demo_seed.py tests/test_demo_seed.py`, then repeat this step.

- [ ] **Step 5: Commit**

Run:

```bash
git add app/demo_seed.py tests/test_demo_seed.py
git commit -m "feat: add local demo seed"
```

## Task 3: Seed Demo Command Wrapper

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/seed_demo.py`
- Test: `tests/test_seed_demo_script.py`

- [ ] **Step 1: Write failing script wiring tests**

Create `tests/test_seed_demo_script.py`:

```python
from app.demo_seed import DemoSeedResult
from scripts import seed_demo


def test_format_seed_summary_includes_demo_ids() -> None:
    text = seed_demo.format_seed_summary(
        DemoSeedResult(
            car_wash_id=1,
            branch_id=1,
            main_service_count=2,
            addon_service_count=3,
            working_hours_count=7,
        )
    )

    assert "Demo data ready." in text
    assert "car_wash_id=1" in text
    assert "branch_id=1" in text
    assert "main_services=2" in text
    assert "addon_services=3" in text
    assert "working_hours=7" in text


async def test_run_seed_uses_settings_defaults(monkeypatch) -> None:
    calls: list[dict[str, int]] = []

    class FakeSettings:
        database_url = "sqlite+aiosqlite:///:memory:"
        default_car_wash_id = 10
        default_branch_id = 20

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    def fake_sessionmaker():
        return FakeSession()

    def fake_create_sessionmaker(database_url: str):
        assert database_url == "sqlite+aiosqlite:///:memory:"
        return fake_sessionmaker

    async def fake_seed_demo_data(session, *, car_wash_id: int, branch_id: int):
        calls.append({"car_wash_id": car_wash_id, "branch_id": branch_id})
        return DemoSeedResult(car_wash_id, branch_id, 2, 3, 7)

    monkeypatch.setattr(seed_demo, "Settings", FakeSettings)
    monkeypatch.setattr(seed_demo, "create_sessionmaker", fake_create_sessionmaker)
    monkeypatch.setattr(seed_demo, "seed_demo_data", fake_seed_demo_data)

    result = await seed_demo.run_seed()

    assert result.car_wash_id == 10
    assert result.branch_id == 20
    assert calls == [{"car_wash_id": 10, "branch_id": 20}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_seed_demo_script.py -q
```

Expected: FAIL because `scripts.seed_demo` does not exist.

- [ ] **Step 3: Add scripts package and seed command**

Create `scripts/__init__.py`:

```python
"""Project command wrappers."""
```

Create `scripts/seed_demo.py`:

```python
import asyncio

from app.config import Settings
from app.db.session import create_sessionmaker
from app.demo_seed import DemoSeedResult, seed_demo_data


def format_seed_summary(result: DemoSeedResult) -> str:
    return (
        "Demo data ready.\n"
        f"car_wash_id={result.car_wash_id}\n"
        f"branch_id={result.branch_id}\n"
        f"main_services={result.main_service_count}\n"
        f"addon_services={result.addon_service_count}\n"
        f"working_hours={result.working_hours_count}"
    )


async def run_seed() -> DemoSeedResult:
    settings = Settings()
    sessionmaker = create_sessionmaker(str(settings.database_url))
    async with sessionmaker() as session:
        return await seed_demo_data(
            session,
            car_wash_id=settings.default_car_wash_id,
            branch_id=settings.default_branch_id,
        )


async def async_main() -> None:
    result = await run_seed()
    print(format_seed_summary(result))


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run script tests and checks**

Run:

```bash
python -m pytest tests/test_seed_demo_script.py -q
python -m ruff check scripts tests/test_seed_demo_script.py
python -m ruff format --check scripts tests/test_seed_demo_script.py
```

Expected: all commands pass. If Ruff reports formatting, run `python -m ruff format scripts tests/test_seed_demo_script.py`, then repeat this step.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/__init__.py scripts/seed_demo.py tests/test_seed_demo_script.py
git commit -m "feat: add local demo seed command"
```

## Task 4: Bot Polling Entrypoint

**Files:**
- Create: `app/bot/main.py`
- Test: `tests/bot/test_main.py`

- [ ] **Step 1: Write failing bot main tests**

Create `tests/bot/test_main.py`:

```python
from aiogram import Bot, Dispatcher

from app.bot.main import build_runtime
from app.config import Settings


async def test_build_runtime_creates_bot_dispatcher_and_sessionmaker() -> None:
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        telegram_bot_token="123456:ABCDEF",
        default_car_wash_id=10,
        default_branch_id=20,
        admin_telegram_ids=(1001,),
    )

    runtime = build_runtime(settings)
    try:
        assert isinstance(runtime.bot, Bot)
        assert isinstance(runtime.dispatcher, Dispatcher)
        assert runtime.dispatcher["settings"] is settings
        assert runtime.dispatcher["default_car_wash_id"] == 10
        assert runtime.dispatcher["default_branch_id"] == 20
        assert runtime.dispatcher["admin_telegram_ids"] == (1001,)
        assert runtime.sessionmaker is not None
    finally:
        await runtime.bot.session.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/bot/test_main.py -q
```

Expected: FAIL because `app.bot.main` does not exist.

- [ ] **Step 3: Add polling entrypoint**

Create `app/bot/main.py`:

```python
import asyncio
from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.factory import create_bot, create_dispatcher
from app.config import Settings
from app.db.session import create_sessionmaker


@dataclass(frozen=True, slots=True)
class BotRuntime:
    bot: Bot
    dispatcher: Dispatcher
    sessionmaker: async_sessionmaker[AsyncSession]


def build_runtime(settings: Settings) -> BotRuntime:
    sessionmaker = create_sessionmaker(str(settings.database_url))
    return BotRuntime(
        bot=create_bot(settings),
        dispatcher=create_dispatcher(settings=settings, sessionmaker=sessionmaker),
        sessionmaker=sessionmaker,
    )


async def run_polling(settings: Settings | None = None) -> None:
    runtime = build_runtime(settings or Settings())
    try:
        await runtime.dispatcher.start_polling(runtime.bot)
    finally:
        await runtime.bot.session.close()


def main() -> None:
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run bot main tests and checks**

Run:

```bash
python -m pytest tests/bot/test_main.py tests/bot/test_factory.py -q
python -m ruff check app/bot/main.py tests/bot/test_main.py
python -m ruff format --check app/bot/main.py tests/bot/test_main.py
python -m mypy app/bot/main.py
```

Expected: all commands pass. If Ruff reports formatting, run `python -m ruff format app/bot/main.py tests/bot/test_main.py`, then repeat this step.

- [ ] **Step 5: Commit**

Run:

```bash
git add app/bot/main.py tests/bot/test_main.py
git commit -m "feat: add bot polling entrypoint"
```

## Task 5: README Local Runbook

**Files:**
- Create: `README.md`
- Modify: `tests/test_local_demo_files.py`

- [ ] **Step 1: Add failing README assertions**

Append to `tests/test_local_demo_files.py`:

```python
def test_readme_documents_local_demo_runbook() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "python -m alembic upgrade head" in text
    assert "python -m scripts.seed_demo" in text
    assert "python -m app.bot.main" in text
    assert ".env.local.example" in text
    assert "TELEGRAM_BOT_TOKEN" in text
    assert "ADMIN_TELEGRAM_IDS" in text
    assert "sqlite+aiosqlite:///data/washbot.local.db" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_local_demo_files.py -q
```

Expected: FAIL because `README.md` does not exist.

- [ ] **Step 3: Add README**

Create `README.md`:

```markdown
# WashBot

Telegram-first booking automation for car washes.

## Local Telegram Demo

This runbook starts the MVP locally with SQLite. It is intended for manual Telegram testing before server deployment.

### 1. Install dependencies

```bash
python -m pip install -e ".[dev]"
```

### 2. Create local environment file

```bash
copy .env.local.example .env
```

Set these values in `.env`:

```env
TELEGRAM_BOT_TOKEN=replace-me
ADMIN_TELEGRAM_IDS=replace-with-your-telegram-user-id
```

`ADMIN_TELEGRAM_IDS` controls who receives admin notifications and who can press admin buttons such as `Сегодня`, `Подтвердить`, and `Отменить`.

For the first local test, get your numeric Telegram user ID from a Telegram ID helper bot and put it into `ADMIN_TELEGRAM_IDS`.

The local database URL is:

```env
DATABASE_URL=sqlite+aiosqlite:///data/washbot.local.db
```

### 3. Prepare the local database

Create the local data directory:

```bash
mkdir data
```

Run migrations:

```bash
python -m alembic upgrade head
```

Seed demo data:

```bash
python -m scripts.seed_demo
```

The seed creates one demo car wash, one branch, working hours from 10:00 to 20:00, main services, and add-on services.

### 4. Start the bot

```bash
python -m app.bot.main
```

### 5. Manual test scenario

1. Open your bot in Telegram.
2. Press `Записаться`.
3. Select a main service.
4. Select add-ons or continue without add-ons.
5. Select date and time.
6. Enter name, phone, and vehicle plate.
7. Confirm the booking.
8. Check that the configured admin receives a new-booking notification.
9. As admin, press `Сегодня`.
10. As admin, press `Подтвердить` or `Отменить`.

## Quality Gate

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy app
```
```

- [ ] **Step 4: Run README test and checks**

Run:

```bash
python -m pytest tests/test_local_demo_files.py -q
python -m ruff check tests/test_local_demo_files.py
python -m ruff format --check tests/test_local_demo_files.py
```

Expected: all commands pass. If Ruff reports formatting, run `python -m ruff format tests/test_local_demo_files.py`, then repeat this step.

- [ ] **Step 5: Commit**

Run:

```bash
git add README.md tests/test_local_demo_files.py
git commit -m "docs: add local demo runbook"
```

## Task 6: Full Quality Gate And Push

**Files:**
- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run all tests**

Run:

```bash
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Ruff lint**

Run:

```bash
python -m ruff check .
```

Expected: no lint errors.

- [ ] **Step 3: Run Ruff format check**

Run:

```bash
python -m ruff format --check .
```

Expected: no files need formatting.

- [ ] **Step 4: Run mypy**

Run:

```bash
python -m mypy app
```

Expected: no type errors.

- [ ] **Step 5: Commit verification fixes if any**

If fixes were required:

```bash
git add .
git commit -m "chore: pass local demo quality gate"
```

If no files changed, do not create an empty commit.

- [ ] **Step 6: Push branch**

Run with the configured GitHub SSH key:

```bash
$sshDir = Join-Path $HOME '.ssh'
$knownHosts = Join-Path $sshDir 'known_hosts'
$key = Join-Path $sshDir 'github_washbot_ed25519'
$env:GIT_SSH_COMMAND = "ssh -i `"$key`" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=`"$knownHosts`""
git push
```

Expected: branch updates on `origin/feature/admin-booking-notifications`.

## Self-Review

Spec coverage:

- Local SQLite config: Task 1.
- Bot polling entrypoint: Task 4.
- Repeatable demo seed: Tasks 2 and 3.
- README runbook: Task 5.
- Ignored local database directory: Task 1.
- Tests for seed and launch wiring: Tasks 1 through 5.
- Quality gate: Task 6.

Completeness scan:

- No incomplete implementation steps remain.

Type consistency:

- `DemoSeedResult` is defined in Task 2 and consumed by Task 3.
- `build_runtime` returns `BotRuntime`, and tests use the same attribute names.
- `sync_database_url` is defined in `app/db/url.py` and imported by `migrations/env.py`.
