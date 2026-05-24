# WashBot Local Demo Launch Design

## 1. Purpose

This feature makes the current Telegram MVP runnable by a developer or product owner on a
local machine without a server. The goal is to test the real Telegram flow end to end:

- customer opens the bot and creates a booking;
- admin receives a new-booking notification;
- admin opens today's bookings;
- admin confirms or cancels the booking.

The first manual demo will use a local SQLite database file. PostgreSQL and server deployment
remain separate future steps.

## 2. Scope

Included:

- local SQLite configuration example;
- bot polling entrypoint;
- repeatable demo seed command;
- README with exact local run steps;
- local database directory ignored by git;
- tests for demo seed behavior and launch wiring.

Not included:

- production server deployment;
- Docker Compose;
- PostgreSQL setup;
- webhook mode;
- background notification worker;
- admin web panel;
- real payment or CRM integration.

## 3. Local Environment

Add `.env.local.example` for the first manual run:

```env
APP_ENV=local
DATABASE_URL=sqlite+aiosqlite:///data/washbot.local.db
TELEGRAM_BOT_TOKEN=replace-me
DEFAULT_REMINDER_BEFORE_MINUTES=60
DEFAULT_CAR_WASH_ID=1
DEFAULT_BRANCH_ID=1
ADMIN_TELEGRAM_IDS=
```

The user copies this file to `.env`, inserts the Telegram bot token, and inserts their Telegram
user ID into `ADMIN_TELEGRAM_IDS`.

The `data/` directory must be ignored by git because it will contain local SQLite files.

## 4. Bot Entrypoint

Add `app/bot/main.py` as the polling entrypoint.

Responsibilities:

- load `Settings`;
- create the async SQLAlchemy sessionmaker from `settings.database_url`;
- create the aiogram `Bot`;
- create the dispatcher through the existing `create_dispatcher`;
- start polling.

The entrypoint should be runnable with:

```bash
python -m app.bot.main
```

The entrypoint should not create demo data automatically. Demo data belongs to the seed command
so that startup remains predictable.

## 5. Demo Seed

Add a script under `scripts/` that can be run with:

```bash
python -m scripts.seed_demo
```

The seed command should:

- load `Settings`;
- create a database session;
- create demo rows if they do not already exist;
- print a short summary of created or reused demo IDs.

Demo data:

- car wash:
  - `id=1` when possible;
  - name: `Demo Wash`;
  - `confirmation_mode=manual`;
  - `reminder_before_minutes=60`.
- branch:
  - default branch for car wash `1`;
  - title: `Main`;
  - address: `Demo street`;
  - `bay_count=1`.
- working hours:
  - every weekday from `10:00` to `20:00`.
- main services:
  - `Стандартная мойка`, 60 minutes, 900 rubles;
  - `Комплекс`, 90 minutes, 1500 rubles.
- add-on services:
  - `Воск`, 15 minutes, 250 rubles;
  - `Чернение шин`, 10 minutes, 200 rubles;
  - `Уборка салона`, 30 minutes, 700 rubles.

The seed must be idempotent. Re-running it should not create duplicate car washes, branches,
working hours, or services.

## 6. Database Setup

The manual flow uses Alembic before seed:

```bash
python -m alembic upgrade head
python -m scripts.seed_demo
```

No automatic migration should run inside the bot polling entrypoint. Keeping migration and
startup separate prevents hidden schema changes during launch.

## 7. README Runbook

Add `README.md` with a short local runbook:

1. Install dependencies.
2. Copy `.env.local.example` to `.env`.
3. Insert `TELEGRAM_BOT_TOKEN`.
4. Insert Telegram admin ID into `ADMIN_TELEGRAM_IDS`.
5. Run Alembic migrations.
6. Run demo seed.
7. Start bot polling.
8. Test the Telegram scenario.

The README should also explain how to get a Telegram user ID in a practical way. For the MVP
runbook, it is acceptable to recommend using a Telegram ID helper bot or temporarily reading the
ID from bot logs once logging is added in a later step.

## 8. Error Handling

Expected failures:

- missing `TELEGRAM_BOT_TOKEN`: settings validation fails before polling;
- missing `ADMIN_TELEGRAM_IDS`: customer booking still works, but admin notifications are skipped;
- missing migrations: seed or runtime database access fails clearly;
- repeated seed command: data is reused instead of duplicated.

The seed command should not swallow database programming errors. If schema or connection setup is
wrong, the command should fail so the setup issue is visible.

## 9. Testing Strategy

Tests should cover:

- demo seed creates the expected car wash, branch, services, and working hours;
- demo seed is idempotent;
- seeded car wash uses manual confirmation mode so admin confirm buttons appear;
- bot entrypoint helper builds `Bot`, dispatcher, and sessionmaker from settings without starting
  polling in tests;
- `.env.local.example` documents the local SQLite URL and admin IDs setting.

Quality gate:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy app
```

## 10. Acceptance Criteria

This feature is complete when:

- a developer can create `.env` from `.env.local.example`;
- local SQLite database files go under ignored `data/`;
- Alembic can prepare the local database;
- demo seed creates one usable car wash setup;
- bot starts with `python -m app.bot.main`;
- customer booking can be tested in Telegram;
- configured admin receives the new-booking notification;
- admin can use `Сегодня`, `Подтвердить`, and `Отменить`;
- automated tests cover the local launch helpers and seed behavior.

## Self-Review

- Completeness scan: no incomplete requirements remain.
- Scope check: focused on local SQLite manual demo only.
- Consistency check: migrations and seed are explicit commands; bot startup does not mutate schema.
- Ambiguity check: first demo uses manual confirmation mode so admin confirm behavior is visible.
