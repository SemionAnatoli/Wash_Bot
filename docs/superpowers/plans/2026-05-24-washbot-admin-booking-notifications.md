# WashBot Admin Booking Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notify configured Telegram admins about new bookings and let admins view today's bookings, confirm pending bookings, and cancel active bookings.

**Architecture:** Keep admin Telegram code in a separate `app/bot/admin_bookings` adapter package. Add an `AdminBookingService` over repository helpers for permission checks, today listing, booking details, and status changes. Customer booking confirmation remains customer-focused and calls a small admin notifier after successful booking creation; notification failures do not undo the customer booking.

**Tech Stack:** Python 3.12, aiogram 3.13.1, SQLAlchemy async ORM, Pydantic Settings, pytest, Ruff, mypy.

---

## Scope Notes

This plan implements the minimum admin operational loop:

- admin IDs from `.env`;
- notification after customer booking creation;
- today view;
- confirm pending bookings;
- cancel pending/confirmed bookings.

It does not implement manual booking creation, blocked slots, service editing, retry worker delivery, or a web admin panel.

## File Structure

Create or modify:

- `app/config/settings.py`: parse admin Telegram IDs.
- `.env.example`: document `ADMIN_TELEGRAM_IDS`.
- `tests/test_settings.py`: settings coverage.
- `app/db/repositories.py`: admin booking query and conditional status update helpers.
- `app/services/admin_booking.py`: admin DTOs, access check, today list, details, confirm/cancel actions.
- `tests/services/test_admin_booking.py`: service tests.
- `app/bot/admin_bookings/__init__.py`: package marker.
- `app/bot/admin_bookings/callbacks.py`: admin callback constants/builders/parsers.
- `app/bot/admin_bookings/messages.py`: Russian admin texts and formatters.
- `app/bot/admin_bookings/keyboards.py`: inline admin action keyboards.
- `tests/bot/admin_bookings/test_callbacks.py`: callback tests.
- `tests/bot/admin_bookings/test_messages.py`: formatter tests.
- `tests/bot/admin_bookings/test_keyboards.py`: keyboard tests.
- `app/bot/admin_bookings/handlers.py`: admin callback handlers.
- `tests/bot/admin_bookings/fakes.py`: fake callback/message/service objects.
- `tests/bot/admin_bookings/test_handlers.py`: admin handler tests.
- `app/bot/admin_bookings/notifier.py`: admin notification sender.
- `app/bot/dependencies.py`: inject `AdminBookingService` and notifier.
- `app/bot/factory.py`: include admin router and admin IDs.
- `tests/bot/test_factory.py`: dispatcher wiring tests.
- `app/bot/customer_booking/handlers.py`: call notifier after successful booking creation.
- `tests/bot/customer_booking/fakes.py`: fake notifier support.
- `tests/bot/customer_booking/test_handlers.py`: notification integration tests.

## Task 1: Admin IDs In Settings

**Files:**
- Modify: `app/config/settings.py`
- Modify: `.env.example`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing settings tests**

Append to `tests/test_settings.py`:

```python
import pytest
from pydantic import ValidationError


def test_settings_parse_admin_telegram_ids_from_comma_string() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
        admin_telegram_ids="1001, 1002",
    )

    assert settings.admin_telegram_ids == (1001, 1002)


def test_settings_default_admin_telegram_ids_is_empty() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
    )

    assert settings.admin_telegram_ids == ()


def test_settings_reject_invalid_admin_telegram_ids() -> None:
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
            telegram_bot_token="token",
            admin_telegram_ids="1001,not-a-number",
        )
```

- [ ] **Step 2: Run settings tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_settings.py -q
```

Expected: FAIL because `admin_telegram_ids` does not exist.

- [ ] **Step 3: Add settings field and parser**

Modify `app/config/settings.py`:

```python
from typing import Any

from pydantic import AnyUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
```

Add field to `Settings`:

```python
    admin_telegram_ids: tuple[int, ...] = Field(default_factory=tuple)
```

Add validator inside `Settings`:

```python
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
```

- [ ] **Step 4: Update env example**

Append to `.env.example`:

```env
ADMIN_TELEGRAM_IDS=
```

- [ ] **Step 5: Run settings tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_settings.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/config/settings.py .env.example tests/test_settings.py
git commit -m "feat: add admin telegram id settings"
```

## Task 2: Admin Booking Service

**Files:**
- Modify: `app/db/repositories.py`
- Create: `app/services/admin_booking.py`
- Test: `tests/services/test_admin_booking.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/services/test_admin_booking.py`:

```python
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, BookingService, Branch, CarWash, Customer, Service
from app.domain.statuses import BookingStatus
from app.services.admin_booking import AdminBookingActionStatus, AdminBookingService


async def seed_booking(
    db_session: AsyncSession,
    *,
    status: str = "pending",
    start_at: datetime = datetime(2026, 5, 24, 10),
) -> tuple[CarWash, Branch, Booking]:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        name="Ivan",
        phone="+79131234567",
        vehicle_plate="A123BC154",
    )
    db_session.add(customer)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=60),
        status=status,
    )
    db_session.add(booking)
    await db_session.flush()
    db_session.add(BookingService(booking_id=booking.id, service_id=service.id, is_main=True))
    await db_session.commit()
    return car_wash, branch, booking


def test_admin_access_uses_configured_ids() -> None:
    service = AdminBookingService(db_session=None, admin_telegram_ids=(1001, 1002))

    assert service.is_admin(1001) is True
    assert service.is_admin(2001) is False


async def test_list_today_bookings_returns_pending_and_confirmed(
    db_session: AsyncSession,
) -> None:
    car_wash, branch, pending = await seed_booking(db_session, status="pending")
    _, _, confirmed = await seed_booking(
        db_session,
        status="confirmed",
        start_at=datetime(2026, 5, 24, 11),
    )
    confirmed.car_wash_id = car_wash.id
    confirmed.branch_id = branch.id
    await db_session.commit()

    bookings = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).list_today_bookings(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        today=date(2026, 5, 24),
    )

    assert [booking.booking_id for booking in bookings] == [pending.id, confirmed.id]
    assert bookings[0].customer_name == "Ivan"
    assert bookings[0].services[0].title == "Standard"


async def test_list_today_bookings_ignores_terminal_statuses(
    db_session: AsyncSession,
) -> None:
    car_wash, branch, _ = await seed_booking(db_session, status="completed")

    bookings = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).list_today_bookings(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        today=date(2026, 5, 24),
    )

    assert bookings == []


async def test_confirm_pending_booking_changes_status(db_session: AsyncSession) -> None:
    car_wash, _, booking = await seed_booking(db_session, status="pending")

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).confirm_booking(car_wash_id=car_wash.id, booking_id=booking.id)

    await db_session.refresh(booking)
    assert result.status == AdminBookingActionStatus.CHANGED
    assert result.booking is not None
    assert result.booking.status == BookingStatus.CONFIRMED.value
    assert booking.status == BookingStatus.CONFIRMED.value


async def test_confirm_non_pending_booking_returns_current_status(
    db_session: AsyncSession,
) -> None:
    car_wash, _, booking = await seed_booking(db_session, status="confirmed")

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).confirm_booking(car_wash_id=car_wash.id, booking_id=booking.id)

    assert result.status == AdminBookingActionStatus.STALE
    assert result.booking is not None
    assert result.booking.status == BookingStatus.CONFIRMED.value


async def test_cancel_active_booking_changes_status(db_session: AsyncSession) -> None:
    car_wash, _, booking = await seed_booking(db_session, status="confirmed")

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).cancel_booking(car_wash_id=car_wash.id, booking_id=booking.id)

    await db_session.refresh(booking)
    assert result.status == AdminBookingActionStatus.CHANGED
    assert result.booking is not None
    assert result.booking.status == BookingStatus.CANCELLED_BY_ADMIN.value
    assert booking.status == BookingStatus.CANCELLED_BY_ADMIN.value


async def test_cancel_terminal_booking_returns_current_status(
    db_session: AsyncSession,
) -> None:
    car_wash, _, booking = await seed_booking(db_session, status="completed")

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).cancel_booking(car_wash_id=car_wash.id, booking_id=booking.id)

    assert result.status == AdminBookingActionStatus.STALE
    assert result.booking is not None
    assert result.booking.status == BookingStatus.COMPLETED.value


async def test_admin_action_rejects_wrong_car_wash(db_session: AsyncSession) -> None:
    _, _, booking = await seed_booking(db_session, status="pending")

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).confirm_booking(car_wash_id=999, booking_id=booking.id)

    assert result.status == AdminBookingActionStatus.NOT_FOUND
    assert result.booking is None
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_admin_booking.py -q
```

Expected: FAIL because `app.services.admin_booking` does not exist.

- [ ] **Step 3: Add repository helpers**

Modify imports in `app/db/repositories.py`:

```python
from sqlalchemy import Select, func, select, update
```

Add helpers:

```python
ADMIN_TODAY_STATUSES = [BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]


async def list_bookings_for_day(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    day_start: datetime,
    day_end: datetime,
) -> list[Booking]:
    result = await session.execute(
        select(Booking)
        .where(
            Booking.car_wash_id == car_wash_id,
            Booking.branch_id == branch_id,
            Booking.status.in_(ADMIN_TODAY_STATUSES),
            Booking.start_at >= day_start,
            Booking.start_at < day_end,
        )
        .order_by(Booking.start_at, Booking.id)
    )
    return list(result.scalars().all())


async def get_booking_with_customer(
    session: AsyncSession,
    *,
    car_wash_id: int,
    booking_id: int,
) -> tuple[Booking, Customer] | None:
    result = await session.execute(
        select(Booking, Customer)
        .join(Customer, Customer.id == Booking.customer_id)
        .where(
            Booking.car_wash_id == car_wash_id,
            Customer.car_wash_id == car_wash_id,
            Booking.id == booking_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    return row[0], row[1]


async def update_booking_status_if_current(
    session: AsyncSession,
    *,
    booking_id: int,
    current_statuses: list[str],
    new_status: str,
) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(Booking)
            .where(
                Booking.id == booking_id,
                Booking.status.in_(current_statuses),
            )
            .values(status=new_status)
            .execution_options(synchronize_session=False)
        ),
    )
    return result.rowcount == 1
```

- [ ] **Step 4: Add admin booking service**

Create `app/services/admin_booking.py`:

```python
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.domain.statuses import BookingStatus, ensure_transition_allowed
from app.services.customer_booking import ServiceOption


@dataclass(frozen=True, slots=True)
class AdminBookingDetails:
    booking_id: int
    status: str
    start_at: datetime
    end_at: datetime
    customer_name: str
    customer_phone: str
    vehicle_plate: str
    services: list[ServiceOption]

    @property
    def total_price(self) -> Decimal:
        return sum((service.price for service in self.services), Decimal("0"))

    @property
    def total_duration_minutes(self) -> int:
        return sum(service.duration_minutes for service in self.services)


class AdminBookingActionStatus(StrEnum):
    CHANGED = "changed"
    STALE = "stale"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class AdminBookingActionResult:
    status: AdminBookingActionStatus
    booking: AdminBookingDetails | None


def _to_service_option(service) -> ServiceOption:
    return ServiceOption(
        id=service.id,
        title=service.title,
        category=service.category,
        price=service.price,
        duration_minutes=service.duration_minutes,
        is_addon=service.is_addon,
    )


class AdminBookingService:
    def __init__(
        self,
        session: AsyncSession | None,
        *,
        admin_telegram_ids: tuple[int, ...],
    ) -> None:
        self._session = session
        self._admin_telegram_ids = set(admin_telegram_ids)

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self._admin_telegram_ids

    async def list_today_bookings(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        today: date,
    ) -> list[AdminBookingDetails]:
        if self._session is None:
            raise RuntimeError("Database session is required.")
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)
        bookings = await repositories.list_bookings_for_day(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            day_start=day_start,
            day_end=day_end,
        )
        return [
            await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking.id)
            for booking in bookings
        ]

    async def get_booking_details(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingDetails | None:
        if self._session is None:
            raise RuntimeError("Database session is required.")
        row = await repositories.get_booking_with_customer(
            self._session,
            car_wash_id=car_wash_id,
            booking_id=booking_id,
        )
        if row is None:
            return None
        booking, customer = row
        service_rows = await repositories.list_booking_services(
            self._session,
            car_wash_id=car_wash_id,
            booking_id=booking.id,
        )
        return AdminBookingDetails(
            booking_id=booking.id,
            status=booking.status,
            start_at=booking.start_at,
            end_at=booking.end_at,
            customer_name=customer.name,
            customer_phone=customer.phone,
            vehicle_plate=customer.vehicle_plate,
            services=[_to_service_option(service) for _, service in service_rows],
        )

    async def confirm_booking(self, *, car_wash_id: int, booking_id: int) -> AdminBookingActionResult:
        booking = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
        if booking is None:
            return AdminBookingActionResult(AdminBookingActionStatus.NOT_FOUND, None)
        if booking.status != BookingStatus.PENDING.value:
            return AdminBookingActionResult(AdminBookingActionStatus.STALE, booking)

        ensure_transition_allowed(BookingStatus(booking.status), BookingStatus.CONFIRMED)
        changed = await repositories.update_booking_status_if_current(
            self._session,
            booking_id=booking_id,
            current_statuses=[BookingStatus.PENDING.value],
            new_status=BookingStatus.CONFIRMED.value,
        )
        if not changed:
            current = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
            return AdminBookingActionResult(AdminBookingActionStatus.STALE, current)
        await self._session.commit()
        current = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
        return AdminBookingActionResult(AdminBookingActionStatus.CHANGED, current)

    async def cancel_booking(self, *, car_wash_id: int, booking_id: int) -> AdminBookingActionResult:
        booking = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
        if booking is None:
            return AdminBookingActionResult(AdminBookingActionStatus.NOT_FOUND, None)
        if booking.status not in {BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value}:
            return AdminBookingActionResult(AdminBookingActionStatus.STALE, booking)

        ensure_transition_allowed(BookingStatus(booking.status), BookingStatus.CANCELLED_BY_ADMIN)
        changed = await repositories.update_booking_status_if_current(
            self._session,
            booking_id=booking_id,
            current_statuses=[BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value],
            new_status=BookingStatus.CANCELLED_BY_ADMIN.value,
        )
        if not changed:
            current = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
            return AdminBookingActionResult(AdminBookingActionStatus.STALE, current)
        await self._session.commit()
        current = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
        return AdminBookingActionResult(AdminBookingActionStatus.CHANGED, current)
```

- [ ] **Step 5: Run service tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_admin_booking.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db/repositories.py app/services/admin_booking.py tests/services/test_admin_booking.py
git commit -m "feat: add admin booking service"
```

## Task 3: Admin Bot Helpers

**Files:**
- Create: `app/bot/admin_bookings/__init__.py`
- Create: `app/bot/admin_bookings/callbacks.py`
- Create: `app/bot/admin_bookings/messages.py`
- Create: `app/bot/admin_bookings/keyboards.py`
- Test: `tests/bot/admin_bookings/test_callbacks.py`
- Test: `tests/bot/admin_bookings/test_messages.py`
- Test: `tests/bot/admin_bookings/test_keyboards.py`

- [ ] **Step 1: Write failing helper tests**

Create `tests/bot/admin_bookings/test_callbacks.py`:

```python
from app.bot.admin_bookings.callbacks import (
    ADMIN_TODAY_CALLBACK,
    build_admin_cancel_callback,
    build_admin_confirm_callback,
    parse_admin_booking_id,
)


def test_admin_callbacks_are_stable() -> None:
    assert ADMIN_TODAY_CALLBACK == "admin:today"
    assert build_admin_confirm_callback(15) == "admin:confirm:15"
    assert build_admin_cancel_callback(15) == "admin:cancel:15"
    assert parse_admin_booking_id("admin:confirm:15", prefix="admin:confirm") == 15
    assert parse_admin_booking_id("admin:cancel:15", prefix="admin:cancel") == 15
```

Create `tests/bot/admin_bookings/test_messages.py`:

```python
from datetime import datetime
from decimal import Decimal

from app.bot.admin_bookings.messages import (
    ADMIN_ACCESS_DENIED_TEXT,
    ADMIN_BOOKING_NOT_FOUND_TEXT,
    ADMIN_TODAY_EMPTY_TEXT,
    format_admin_booking_details,
    format_admin_today_bookings,
)
from app.services.admin_booking import AdminBookingDetails
from app.services.customer_booking import ServiceOption


def option(service_id: int, title: str, price: str, duration: int) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="wash",
        price=Decimal(price),
        duration_minutes=duration,
        is_addon=False,
    )


def details(status: str = "pending") -> AdminBookingDetails:
    return AdminBookingDetails(
        booking_id=15,
        status=status,
        start_at=datetime(2026, 5, 24, 10),
        end_at=datetime(2026, 5, 24, 11),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        services=[option(1, "Standard", "900", 60)],
    )


def test_admin_static_texts_are_stable() -> None:
    assert ADMIN_ACCESS_DENIED_TEXT == "Недостаточно прав."
    assert ADMIN_TODAY_EMPTY_TEXT == "Сегодня записей нет."
    assert ADMIN_BOOKING_NOT_FOUND_TEXT == "Запись не найдена или уже недоступна."


def test_format_admin_booking_details_contains_customer_and_services() -> None:
    text = format_admin_booking_details(details())

    assert "Новая запись" in text
    assert "24.05.2026 10:00" in text
    assert "Ожидает подтверждения" in text
    assert "Ivan" in text
    assert "+79131234567" in text
    assert "A123BC154" in text
    assert "Standard" in text
    assert "900 руб." in text


def test_format_admin_booking_details_escapes_html() -> None:
    booking = AdminBookingDetails(
        booking_id=15,
        status="confirmed",
        start_at=datetime(2026, 5, 24, 10),
        end_at=datetime(2026, 5, 24, 11),
        customer_name="A < B",
        customer_phone="+7&913",
        vehicle_plate="A<123>",
        services=[option(1, "Wash <Pro> & Wax", "900", 60)],
    )

    text = format_admin_booking_details(booking)

    assert "A &lt; B" in text
    assert "+7&amp;913" in text
    assert "A&lt;123&gt;" in text
    assert "Wash &lt;Pro&gt; &amp; Wax" in text


def test_format_admin_today_bookings_lists_entries() -> None:
    text = format_admin_today_bookings([details(status="confirmed")])

    assert "Сегодняшние записи" in text
    assert "10:00" in text
    assert "Подтверждена" in text
    assert "A123BC154" in text
```

Create `tests/bot/admin_bookings/test_keyboards.py`:

```python
from app.bot.admin_bookings.callbacks import ADMIN_TODAY_CALLBACK
from app.bot.admin_bookings.keyboards import admin_booking_actions_keyboard, admin_today_keyboard


def callback_grid(markup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def text_grid(markup) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard]


def test_pending_booking_keyboard_contains_confirm_cancel_today() -> None:
    markup = admin_booking_actions_keyboard(booking_id=15, status="pending")

    assert callback_grid(markup) == [
        ["admin:confirm:15"],
        ["admin:cancel:15"],
        [ADMIN_TODAY_CALLBACK],
    ]
    assert text_grid(markup) == [["Подтвердить"], ["Отменить"], ["Сегодня"]]


def test_confirmed_booking_keyboard_omits_confirm() -> None:
    markup = admin_booking_actions_keyboard(booking_id=15, status="confirmed")

    assert callback_grid(markup) == [["admin:cancel:15"], [ADMIN_TODAY_CALLBACK]]


def test_admin_today_keyboard_contains_today_action() -> None:
    markup = admin_today_keyboard()

    assert callback_grid(markup) == [[ADMIN_TODAY_CALLBACK]]
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/admin_bookings -q
```

Expected: FAIL because admin bot package does not exist.

- [ ] **Step 3: Add admin callback helpers**

Create `app/bot/admin_bookings/__init__.py`:

```python
"""Admin booking Telegram flow."""
```

Create `app/bot/admin_bookings/callbacks.py`:

```python
ADMIN_TODAY_CALLBACK = "admin:today"


def build_admin_confirm_callback(booking_id: int) -> str:
    return f"admin:confirm:{booking_id}"


def build_admin_cancel_callback(booking_id: int) -> str:
    return f"admin:cancel:{booking_id}"


def parse_admin_booking_id(data: str, *, prefix: str) -> int:
    expected_prefix = f"{prefix}:"
    if not data.startswith(expected_prefix):
        raise ValueError("Unexpected admin callback prefix.")
    return int(data.removeprefix(expected_prefix))
```

- [ ] **Step 4: Add admin message helpers**

Create `app/bot/admin_bookings/messages.py`:

```python
from html import escape

from app.bot.customer_booking.messages import format_duration, format_money, service_line
from app.services.admin_booking import AdminBookingDetails

ADMIN_ACCESS_DENIED_TEXT = "Недостаточно прав."
ADMIN_TODAY_EMPTY_TEXT = "Сегодня записей нет."
ADMIN_BOOKING_NOT_FOUND_TEXT = "Запись не найдена или уже недоступна."
ADMIN_BOOKING_CONFIRMED_TEXT = "Запись подтверждена."
ADMIN_BOOKING_CANCELLED_TEXT = "Запись отменена администратором."


def admin_status_label(status: str) -> str:
    return {
        "pending": "Ожидает подтверждения",
        "confirmed": "Подтверждена",
        "cancelled_by_admin": "Отменена администратором",
        "cancelled_by_customer": "Отменена клиентом",
        "completed": "Завершена",
        "no_show": "Не приехал",
    }.get(status, status)


def format_admin_booking_details(booking: AdminBookingDetails, *, title: str = "Новая запись") -> str:
    service_lines = "\n".join(f"- {service_line(service)}" for service in booking.services)
    return (
        f"{title}\n\n"
        f"Дата и время: {booking.start_at:%d.%m.%Y %H:%M}\n"
        f"Статус: {escape(admin_status_label(booking.status))}\n"
        f"Услуги:\n{service_lines}\n"
        f"Длительность: {format_duration(booking.total_duration_minutes)}\n"
        f"Итого: {format_money(booking.total_price)}\n\n"
        f"Имя: {escape(booking.customer_name)}\n"
        f"Телефон: {escape(booking.customer_phone)}\n"
        f"Авто: {escape(booking.vehicle_plate)}"
    )


def format_admin_today_bookings(bookings: list[AdminBookingDetails]) -> str:
    if not bookings:
        return ADMIN_TODAY_EMPTY_TEXT
    lines = ["Сегодняшние записи:"]
    for booking in bookings:
        lines.append(
            f"{booking.start_at:%H:%M} — {escape(booking.vehicle_plate)}, "
            f"{escape(admin_status_label(booking.status))}"
        )
    return "\n".join(lines)
```

- [ ] **Step 5: Add admin keyboards**

Create `app/bot/admin_bookings/keyboards.py`:

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.admin_bookings.callbacks import (
    ADMIN_TODAY_CALLBACK,
    build_admin_cancel_callback,
    build_admin_confirm_callback,
)


def _markup(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_booking_actions_keyboard(*, booking_id: int, status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if status == "pending":
        rows.append(
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=build_admin_confirm_callback(booking_id),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Отменить",
                callback_data=build_admin_cancel_callback(booking_id),
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="Сегодня", callback_data=ADMIN_TODAY_CALLBACK)])
    return _markup(rows)


def admin_today_keyboard() -> InlineKeyboardMarkup:
    return _markup([[InlineKeyboardButton(text="Сегодня", callback_data=ADMIN_TODAY_CALLBACK)]])
```

- [ ] **Step 6: Run helper tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/admin_bookings/test_callbacks.py tests/bot/admin_bookings/test_messages.py tests/bot/admin_bookings/test_keyboards.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/bot/admin_bookings tests/bot/admin_bookings/test_callbacks.py tests/bot/admin_bookings/test_messages.py tests/bot/admin_bookings/test_keyboards.py
git commit -m "feat: add admin booking bot helpers"
```

## Task 4: Admin Booking Handlers And Router Wiring

**Files:**
- Create: `app/bot/admin_bookings/fakes.py`
- Create: `app/bot/admin_bookings/handlers.py`
- Modify: `app/bot/factory.py`
- Modify: `app/bot/dependencies.py`
- Test: `tests/bot/admin_bookings/test_handlers.py`
- Test: `tests/bot/test_factory.py`

- [ ] **Step 1: Write failing admin handler tests**

Create `tests/bot/admin_bookings/fakes.py`:

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.admin_booking import (
    AdminBookingActionResult,
    AdminBookingActionStatus,
    AdminBookingDetails,
)
from app.services.customer_booking import ServiceOption


@dataclass
class FakeTelegramUser:
    id: int = 1001
    username: str | None = "admin"


@dataclass
class FakeMessage:
    answers: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str
    from_user: FakeTelegramUser | None = field(default_factory=FakeTelegramUser)
    message: FakeMessage = field(default_factory=FakeMessage)
    answered: bool = False

    async def answer(self) -> None:
        self.answered = True


def service_option() -> ServiceOption:
    return ServiceOption(
        id=1,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
    )


def booking_details(status: str = "pending") -> AdminBookingDetails:
    return AdminBookingDetails(
        booking_id=15,
        status=status,
        start_at=datetime(2026, 5, 24, 10),
        end_at=datetime(2026, 5, 24, 11),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        services=[service_option()],
    )


@dataclass
class FakeAdminBookingService:
    admin_ids: set[int] = field(default_factory=lambda: {1001})
    today_bookings: list[AdminBookingDetails] = field(default_factory=lambda: [booking_details()])
    confirm_result: AdminBookingActionResult = field(
        default_factory=lambda: AdminBookingActionResult(
            AdminBookingActionStatus.CHANGED,
            booking_details(status="confirmed"),
        )
    )
    cancel_result: AdminBookingActionResult = field(
        default_factory=lambda: AdminBookingActionResult(
            AdminBookingActionStatus.CHANGED,
            booking_details(status="cancelled_by_admin"),
        )
    )
    today_requests: list[dict[str, Any]] = field(default_factory=list)
    confirm_requests: list[dict[str, Any]] = field(default_factory=list)
    cancel_requests: list[dict[str, Any]] = field(default_factory=list)

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self.admin_ids

    async def list_today_bookings(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        today: date,
    ) -> list[AdminBookingDetails]:
        self.today_requests.append(
            {"car_wash_id": car_wash_id, "branch_id": branch_id, "today": today}
        )
        return self.today_bookings

    async def confirm_booking(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingActionResult:
        self.confirm_requests.append({"car_wash_id": car_wash_id, "booking_id": booking_id})
        return self.confirm_result

    async def cancel_booking(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingActionResult:
        self.cancel_requests.append({"car_wash_id": car_wash_id, "booking_id": booking_id})
        return self.cancel_result
```

Create `tests/bot/admin_bookings/test_handlers.py`:

```python
from datetime import date

from app.bot.admin_bookings.handlers import (
    handle_admin_booking_cancelled,
    handle_admin_booking_confirmed,
    handle_admin_today_requested,
    router,
)
from app.bot.admin_bookings.messages import ADMIN_ACCESS_DENIED_TEXT, ADMIN_TODAY_EMPTY_TEXT
from app.services.admin_booking import AdminBookingActionResult, AdminBookingActionStatus
from tests.bot.admin_bookings.fakes import FakeAdminBookingService, FakeCallbackQuery, booking_details


def first_text(callback: FakeCallbackQuery) -> str:
    return callback.message.answers[0]["text"]


async def test_today_denies_non_admin() -> None:
    callback = FakeCallbackQuery(data="admin:today")
    service = FakeAdminBookingService(admin_ids=set())

    await handle_admin_today_requested(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert first_text(callback) == ADMIN_ACCESS_DENIED_TEXT
    assert service.today_requests == []


async def test_today_shows_admin_bookings() -> None:
    callback = FakeCallbackQuery(data="admin:today")
    service = FakeAdminBookingService()

    await handle_admin_today_requested(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert service.today_requests[0]["car_wash_id"] == 10
    assert service.today_requests[0]["branch_id"] == 20
    assert service.today_requests[0]["today"] == date.today()
    assert "Сегодняшние записи" in first_text(callback)


async def test_today_empty_state() -> None:
    callback = FakeCallbackQuery(data="admin:today")
    service = FakeAdminBookingService(today_bookings=[])

    await handle_admin_today_requested(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert first_text(callback) == ADMIN_TODAY_EMPTY_TEXT


async def test_confirm_booking_changes_pending_for_admin() -> None:
    callback = FakeCallbackQuery(data="admin:confirm:15")
    service = FakeAdminBookingService()

    await handle_admin_booking_confirmed(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert service.confirm_requests == [{"car_wash_id": 10, "booking_id": 15}]
    assert "Запись подтверждена" in first_text(callback)


async def test_confirm_booking_denies_non_admin() -> None:
    callback = FakeCallbackQuery(data="admin:confirm:15")
    service = FakeAdminBookingService(admin_ids=set())

    await handle_admin_booking_confirmed(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert first_text(callback) == ADMIN_ACCESS_DENIED_TEXT
    assert service.confirm_requests == []


async def test_cancel_booking_changes_active_for_admin() -> None:
    callback = FakeCallbackQuery(data="admin:cancel:15")
    service = FakeAdminBookingService()

    await handle_admin_booking_cancelled(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert service.cancel_requests == [{"car_wash_id": 10, "booking_id": 15}]
    assert "Запись отменена" in first_text(callback)


async def test_stale_confirm_shows_current_state() -> None:
    callback = FakeCallbackQuery(data="admin:confirm:15")
    service = FakeAdminBookingService(
        confirm_result=AdminBookingActionResult(
            AdminBookingActionStatus.STALE,
            booking_details(status="confirmed"),
        )
    )

    await handle_admin_booking_confirmed(
        callback,
        admin_booking_service=service,
        default_car_wash_id=10,
    )

    assert "Текущее состояние записи" in first_text(callback)
    assert "Подтверждена" in first_text(callback)


def test_admin_router_registers_callbacks() -> None:
    assert len(router.callback_query.handlers) == 3
```

- [ ] **Step 2: Update factory test to fail until admin router is wired**

Modify `tests/bot/test_factory.py` assertion:

```python
    assert any(router.name == "customer_booking" for router in dispatcher.sub_routers)
    assert any(router.name == "admin_bookings" for router in dispatcher.sub_routers)
    assert dispatcher["admin_telegram_ids"] == settings.admin_telegram_ids
```

Create settings with `admin_telegram_ids=(1001,)`.

- [ ] **Step 3: Run handler/factory tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/admin_bookings/test_handlers.py tests/bot/test_factory.py -q
```

Expected: FAIL because admin handlers/router are not implemented or wired.

- [ ] **Step 4: Add admin handlers**

Create `app/bot/admin_bookings/handlers.py`:

```python
from datetime import date
from typing import cast

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.bot.admin_bookings.callbacks import (
    ADMIN_TODAY_CALLBACK,
    parse_admin_booking_id,
)
from app.bot.admin_bookings.keyboards import admin_booking_actions_keyboard
from app.bot.admin_bookings.messages import (
    ADMIN_ACCESS_DENIED_TEXT,
    ADMIN_BOOKING_CANCELLED_TEXT,
    ADMIN_BOOKING_CONFIRMED_TEXT,
    ADMIN_BOOKING_NOT_FOUND_TEXT,
    format_admin_booking_details,
    format_admin_today_bookings,
)
from app.services.admin_booking import (
    AdminBookingActionResult,
    AdminBookingActionStatus,
    AdminBookingService,
)

router = Router(name="admin_bookings")


def _callback_message(callback: CallbackQuery) -> Message:
    if callback.message is None:
        raise RuntimeError("Callback query has no message.")
    return cast(Message, callback.message)


def _telegram_user_id(callback: CallbackQuery) -> int:
    if callback.from_user is None:
        raise RuntimeError("Telegram user is missing.")
    return callback.from_user.id


async def _ensure_admin(callback: CallbackQuery, service: AdminBookingService) -> bool:
    if service.is_admin(_telegram_user_id(callback)):
        return True
    await _callback_message(callback).answer(ADMIN_ACCESS_DENIED_TEXT)
    return False


async def handle_admin_today_requested(
    callback: CallbackQuery,
    *,
    admin_booking_service: AdminBookingService,
    default_car_wash_id: int,
    default_branch_id: int,
) -> None:
    await callback.answer()
    if not await _ensure_admin(callback, admin_booking_service):
        return

    bookings = await admin_booking_service.list_today_bookings(
        car_wash_id=default_car_wash_id,
        branch_id=default_branch_id,
        today=date.today(),
    )
    await _callback_message(callback).answer(format_admin_today_bookings(bookings))


def _action_text(result: AdminBookingActionResult, *, changed_text: str) -> str:
    if result.status == AdminBookingActionStatus.NOT_FOUND or result.booking is None:
        return ADMIN_BOOKING_NOT_FOUND_TEXT
    if result.status == AdminBookingActionStatus.STALE:
        return format_admin_booking_details(result.booking, title="Текущее состояние записи")
    return f"{changed_text}\n\n{format_admin_booking_details(result.booking, title='Текущее состояние записи')}"


async def handle_admin_booking_confirmed(
    callback: CallbackQuery,
    *,
    admin_booking_service: AdminBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    if not await _ensure_admin(callback, admin_booking_service):
        return

    booking_id = parse_admin_booking_id(callback.data or "", prefix="admin:confirm")
    result = await admin_booking_service.confirm_booking(
        car_wash_id=default_car_wash_id,
        booking_id=booking_id,
    )
    reply_markup = (
        admin_booking_actions_keyboard(booking_id=result.booking.booking_id, status=result.booking.status)
        if result.booking is not None
        else None
    )
    await _callback_message(callback).answer(
        _action_text(result, changed_text=ADMIN_BOOKING_CONFIRMED_TEXT),
        reply_markup=reply_markup,
    )


async def handle_admin_booking_cancelled(
    callback: CallbackQuery,
    *,
    admin_booking_service: AdminBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    if not await _ensure_admin(callback, admin_booking_service):
        return

    booking_id = parse_admin_booking_id(callback.data or "", prefix="admin:cancel")
    result = await admin_booking_service.cancel_booking(
        car_wash_id=default_car_wash_id,
        booking_id=booking_id,
    )
    reply_markup = (
        admin_booking_actions_keyboard(booking_id=result.booking.booking_id, status=result.booking.status)
        if result.booking is not None
        else None
    )
    await _callback_message(callback).answer(
        _action_text(result, changed_text=ADMIN_BOOKING_CANCELLED_TEXT),
        reply_markup=reply_markup,
    )


router.callback_query.register(handle_admin_today_requested, F.data == ADMIN_TODAY_CALLBACK)
router.callback_query.register(handle_admin_booking_confirmed, F.data.startswith("admin:confirm:"))
router.callback_query.register(handle_admin_booking_cancelled, F.data.startswith("admin:cancel:"))
```

- [ ] **Step 5: Inject admin service and router**

Modify `app/bot/dependencies.py`:

```python
from app.services.admin_booking import AdminBookingService
```

Inside middleware before return:

```python
            admin_telegram_ids = tuple(data.get("admin_telegram_ids", ()))
            data["admin_booking_service"] = AdminBookingService(
                session,
                admin_telegram_ids=admin_telegram_ids,
            )
```

Modify `app/bot/factory.py`:

```python
from app.bot.admin_bookings.handlers import router as admin_bookings_router
```

Inside `create_dispatcher`:

```python
    dispatcher["admin_telegram_ids"] = settings.admin_telegram_ids
    dispatcher.include_router(admin_bookings_router)
```

Keep customer router included too.

- [ ] **Step 6: Run admin handler/factory tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/admin_bookings/test_handlers.py tests/bot/test_factory.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/bot/admin_bookings/handlers.py app/bot/dependencies.py app/bot/factory.py tests/bot/admin_bookings/fakes.py tests/bot/admin_bookings/test_handlers.py tests/bot/test_factory.py
git commit -m "feat: add admin booking handlers"
```

## Task 5: Notify Admins After Customer Booking Creation

**Files:**
- Create: `app/bot/admin_bookings/notifier.py`
- Modify: `app/bot/dependencies.py`
- Modify: `app/bot/customer_booking/handlers.py`
- Modify: `tests/bot/customer_booking/fakes.py`
- Modify: `tests/bot/customer_booking/test_handlers.py`

- [ ] **Step 1: Write failing notifier integration tests**

Modify `tests/bot/customer_booking/fakes.py`:

```python
@dataclass
class FakeAdminBookingNotifier:
    sent_booking_ids: list[int] = field(default_factory=list)
    send_error: Exception | None = None

    async def notify_new_booking(self, *, car_wash_id: int, booking_id: int) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.sent_booking_ids.append(booking_id)
```

Ensure fake booking result includes `id`:

```python
        return type("BookingResult", (), {"id": 42, "status": self.booking_status})()
```

Append to `tests/bot/customer_booking/test_handlers.py`:

```python
from tests.bot.customer_booking.fakes import FakeAdminBookingNotifier


async def test_booking_confirmation_notifies_admin_after_success() -> None:
    service = FakeCustomerBookingService()
    notifier = FakeAdminBookingNotifier()
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [2],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "Иван",
            "customer_phone": "+79131234567",
            "vehicle_plate": "A123BC154",
        }
    )
    callback = FakeCallbackQuery(data="book:confirm")

    await handle_booking_confirmed(
        callback,
        state,
        customer_booking_service=service,
        admin_booking_notifier=notifier,
    )

    assert notifier.sent_booking_ids == [42]
    assert state.cleared is True


async def test_booking_confirmation_keeps_customer_success_when_admin_notification_fails() -> None:
    service = FakeCustomerBookingService()
    notifier = FakeAdminBookingNotifier(send_error=RuntimeError("Telegram failed."))
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "Иван",
            "customer_phone": "+79131234567",
            "vehicle_plate": "A123BC154",
        }
    )
    callback = FakeCallbackQuery(data="book:confirm")

    await handle_booking_confirmed(
        callback,
        state,
        customer_booking_service=service,
        admin_booking_notifier=notifier,
    )

    assert "подтверждена" in first_text(callback.message).lower()
    assert state.cleared is True
```

- [ ] **Step 2: Run customer handler tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -q
```

Expected: FAIL because notifier support does not exist.

- [ ] **Step 3: Add admin notifier**

Create `app/bot/admin_bookings/notifier.py`:

```python
from aiogram import Bot

from app.bot.admin_bookings.keyboards import admin_booking_actions_keyboard
from app.bot.admin_bookings.messages import format_admin_booking_details
from app.services.admin_booking import AdminBookingService


class AdminBookingNotifier:
    def __init__(
        self,
        *,
        bot: Bot,
        admin_booking_service: AdminBookingService,
        admin_telegram_ids: tuple[int, ...],
    ) -> None:
        self._bot = bot
        self._admin_booking_service = admin_booking_service
        self._admin_telegram_ids = admin_telegram_ids

    async def notify_new_booking(self, *, car_wash_id: int, booking_id: int) -> None:
        if not self._admin_telegram_ids:
            return
        booking = await self._admin_booking_service.get_booking_details(
            car_wash_id=car_wash_id,
            booking_id=booking_id,
        )
        if booking is None:
            return
        text = format_admin_booking_details(booking)
        reply_markup = admin_booking_actions_keyboard(
            booking_id=booking.booking_id,
            status=booking.status,
        )
        for admin_id in self._admin_telegram_ids:
            await self._bot.send_message(admin_id, text, reply_markup=reply_markup)
```

- [ ] **Step 4: Inject notifier in middleware**

Modify `app/bot/dependencies.py`:

```python
from aiogram import Bot
from app.bot.admin_bookings.notifier import AdminBookingNotifier
```

Inside middleware:

```python
            admin_booking_service = AdminBookingService(
                session,
                admin_telegram_ids=admin_telegram_ids,
            )
            data["admin_booking_service"] = admin_booking_service
            bot = data.get("bot")
            if isinstance(bot, Bot):
                data["admin_booking_notifier"] = AdminBookingNotifier(
                    bot=bot,
                    admin_booking_service=admin_booking_service,
                    admin_telegram_ids=admin_telegram_ids,
                )
```

- [ ] **Step 5: Call notifier after successful customer booking**

Modify `handle_booking_confirmed` signature in `app/bot/customer_booking/handlers.py`:

```python
    admin_booking_notifier: Any | None = None,
```

After `await state.clear()` and before answering customer:

```python
    if admin_booking_notifier is not None:
        try:
            await admin_booking_notifier.notify_new_booking(
                car_wash_id=int(data["car_wash_id"]),
                booking_id=booking.id,
            )
        except Exception:
            pass
```

This intentionally prevents admin notification delivery failure from undoing customer booking creation.

- [ ] **Step 6: Run customer handler tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/bot/admin_bookings/notifier.py app/bot/dependencies.py app/bot/customer_booking/handlers.py tests/bot/customer_booking/fakes.py tests/bot/customer_booking/test_handlers.py
git commit -m "feat: notify admins about new bookings"
```

## Task 6: Quality Gate

**Files:**
- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run all tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Ruff**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m ruff check .
```

Expected: no errors.

- [ ] **Step 3: Run format check**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m ruff format --check .
```

Expected: no files need formatting.

- [ ] **Step 4: Run type check**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m mypy app
```

Expected: no type errors.

- [ ] **Step 5: Commit verification fixes if any**

If verification required fixes:

```bash
git add .
git commit -m "chore: pass admin booking quality gate"
```

If no files changed, do not create an empty commit.

## Self-Review

Spec coverage:

- Admin IDs from settings: Task 1.
- Admin access isolated for future DB source: Task 2 `AdminBookingService.is_admin`.
- New booking notification: Task 5.
- Admin buttons: Task 3.
- Today view: Tasks 2 and 4.
- Confirm/cancel actions: Tasks 2 and 4.
- Non-admin denial: Task 4.
- Stale status handling: Task 2 action result and Task 4 handler tests.
- Notification failure does not undo customer booking: Task 5.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified implementation steps remain.

Type consistency:

- Callback constants used by keyboards and handlers are defined in Task 3.
- `AdminBookingDetails` and `AdminBookingActionResult` are defined before bot helpers and handlers consume them.
- Middleware injects the same dependency names used by handlers:
  `admin_booking_service` and `admin_booking_notifier`.
