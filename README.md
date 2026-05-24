# WashBot

Telegram-first booking automation for car washes.

## Local Telegram Demo

This runbook starts the MVP locally with SQLite. Use it for manual Telegram testing before
server deployment.

### 1. Install Dependencies

```bash
python -m pip install -e ".[dev]"
```

### 2. Create Local Environment File

```powershell
Copy-Item .env.local.example .env
```

Set these values in `.env`:

```env
TELEGRAM_BOT_TOKEN=replace-me
ADMIN_TELEGRAM_IDS=replace-with-your-telegram-user-id
```

`ADMIN_TELEGRAM_IDS` controls who receives admin notifications and who can press admin buttons
such as `Сегодня`, `Подтвердить`, and `Отменить`.

For the first local test, get your numeric Telegram user ID from a Telegram ID helper bot and put
it into `ADMIN_TELEGRAM_IDS`.

The local database URL is:

```env
DATABASE_URL=sqlite+aiosqlite:///data/washbot.local.db
```

### 3. Prepare The Local Database

Create the local data directory:

```powershell
New-Item -ItemType Directory -Force data
```

Run migrations:

```bash
python -m alembic upgrade head
```

Seed demo data:

```bash
python -m scripts.seed_demo
```

The seed creates one demo car wash, one branch, working hours from 10:00 to 20:00, main services,
and add-on services.

### 4. Start The Bot

```bash
python -m app.bot.main
```

### 5. Manual Test Scenario

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
