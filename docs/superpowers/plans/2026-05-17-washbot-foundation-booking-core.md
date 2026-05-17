# WashBot Foundation And Booking Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first testable backend slice: project scaffold, domain validation, service duration calculation, slot availability, and booking creation against PostgreSQL-ready models.

**Architecture:** Implement a modular monolith with thin future interfaces and a tested core. This plan creates `app/domain`, `app/services`, `app/db`, configuration, migrations, and tests, but does not implement Telegram handlers, notification worker delivery, or Docker deployment yet.

**Tech Stack:** Python 3.12, pytest, Ruff, SQLAlchemy 2.x, Alembic, Pydantic Settings, PostgreSQL-compatible schema.

---

## Scope Notes

The technical design covers several subsystems: booking core, Telegram customer flow, Telegram admin flow, notifications worker, FastAPI API, deployment, and future productization. This plan intentionally covers only the foundation and booking core. Separate follow-up plans should cover:

- Telegram customer booking flow.
- Telegram admin operations.
- Worker and notification processing.
- FastAPI internal API.
- Docker Compose deployment and release checklist.

## File Structure

Create these files:

- `pyproject.toml`: project metadata, dependencies, tool settings.
- `.env.example`: documented environment variables without secrets.
- `alembic.ini`: Alembic configuration.
- `app/__init__.py`: package marker.
- `app/config/__init__.py`: config package marker.
- `app/config/settings.py`: environment settings.
- `app/domain/__init__.py`: domain package marker.
- `app/domain/errors.py`: domain exceptions.
- `app/domain/statuses.py`: booking status enum and transition rules.
- `app/domain/time.py`: time interval helpers.
- `app/domain/validation.py`: customer/admin input validation.
- `app/domain/services.py`: service and add-on duration calculation.
- `app/domain/slots.py`: pure slot availability logic.
- `app/db/__init__.py`: db package marker.
- `app/db/base.py`: SQLAlchemy base.
- `app/db/session.py`: engine/session helpers.
- `app/db/models.py`: SQLAlchemy models.
- `app/db/repositories.py`: focused booking queries.
- `app/services/__init__.py`: services package marker.
- `app/services/booking_service.py`: booking creation use case.
- `migrations/env.py`: Alembic environment.
- `migrations/script.py.mako`: Alembic migration template.
- `migrations/versions/0001_initial_schema.py`: initial database schema.
- `tests/__init__.py`: test package marker.
- `tests/domain/test_validation.py`: validation tests.
- `tests/domain/test_services.py`: service duration tests.
- `tests/domain/test_slots.py`: slot availability tests.
- `tests/domain/test_statuses.py`: status transition tests.
- `tests/services/test_booking_service.py`: booking service tests.

## Task 1: Project Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create project config**

Create `pyproject.toml`:

```toml
[project]
name = "washbot"
version = "0.1.0"
description = "Telegram-first booking automation for car washes"
requires-python = ">=3.12"
dependencies = [
    "aiogram>=3.6,<4",
    "alembic>=1.13,<2",
    "asyncpg>=0.29,<1",
    "fastapi>=0.111,<1",
    "pydantic-settings>=2.2,<3",
    "sqlalchemy>=2.0,<3",
    "uvicorn[standard]>=0.30,<1",
]

[project.optional-dependencies]
dev = [
    "httpx>=0.27,<1",
    "mypy>=1.10,<2",
    "pytest>=8.2,<9",
    "pytest-asyncio>=0.23,<1",
    "ruff>=0.4,<1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["app"]

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"
```

Create `.env.example`:

```env
APP_ENV=local
DATABASE_URL=postgresql+asyncpg://washbot:washbot@localhost:5432/washbot
TELEGRAM_BOT_TOKEN=replace-me
DEFAULT_REMINDER_BEFORE_MINUTES=60
```

Create empty package files:

```python
# app/__init__.py
```

```python
# tests/__init__.py
```

- [ ] **Step 2: Install development dependencies**

Run:

```bash
python -m pip install -e ".[dev]"
```

Expected: dependencies install successfully.

- [ ] **Step 3: Run tooling command**

Run:

```bash
python -m pytest --version
```

Expected: pytest prints its version.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example app/__init__.py tests/__init__.py
git commit -m "chore: add project tooling"
```

## Task 2: Configuration

**Files:**
- Create: `app/config/__init__.py`
- Create: `app/config/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing settings test**

Create `tests/test_settings.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_settings.py -v
```

Expected: FAIL because `app.config.settings` does not exist.

- [ ] **Step 3: Implement settings**

Create `app/config/__init__.py`:

```python
from app.config.settings import Settings

__all__ = ["Settings"]
```

Create `app/config/settings.py`:

```python
from pydantic import AnyUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "local"
    database_url: AnyUrl
    telegram_bot_token: SecretStr
    default_reminder_before_minutes: int = Field(default=60, ge=0, le=1440)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_settings.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/config tests/test_settings.py
git commit -m "chore: add typed settings"
```

## Task 3: Input Validation

**Files:**
- Create: `app/domain/__init__.py`
- Create: `app/domain/errors.py`
- Create: `app/domain/validation.py`
- Test: `tests/domain/test_validation.py`

- [ ] **Step 1: Write failing validation tests**

Create `tests/domain/test_validation.py`:

```python
import pytest

from app.domain.errors import ValidationError
from app.domain.validation import normalize_name, normalize_phone, normalize_vehicle_plate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Иван", "Иван"),
        ("  Ivan Petrov  ", "Ivan Petrov"),
    ],
)
def test_normalize_name_accepts_valid_names(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "A", "x" * 81])
def test_normalize_name_rejects_invalid_names(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalize_name(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+7 913 123-45-67", "+79131234567"),
        ("8 (913) 123-45-67", "+79131234567"),
    ],
)
def test_normalize_phone_accepts_russian_formats(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "+1 555 000 00 00", "8913123456"])
def test_normalize_phone_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalize_phone(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("а123вс154", "А123ВС154"),
        (" A 123 BC 154 ", "A 123 BC 154"),
    ],
)
def test_normalize_vehicle_plate_accepts_soft_plate_format(raw: str, expected: str) -> None:
    assert normalize_vehicle_plate(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "!", "x" * 16])
def test_normalize_vehicle_plate_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalize_vehicle_plate(raw)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_validation.py -v
```

Expected: FAIL because validation module does not exist.

- [ ] **Step 3: Implement validation**

Create `app/domain/__init__.py`:

```python
```

Create `app/domain/errors.py`:

```python
class DomainError(Exception):
    """Base error for expected domain failures."""


class ValidationError(DomainError):
    """Raised when user-provided input is invalid."""
```

Create `app/domain/validation.py`:

```python
import re

from app.domain.errors import ValidationError

_PLATE_PATTERN = re.compile(r"^[0-9A-ZА-ЯЁ -]+$")


def normalize_name(raw: str) -> str:
    value = " ".join(raw.strip().split())
    if len(value) < 2 or len(value) > 80:
        raise ValidationError("Name must be between 2 and 80 characters.")
    return value


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        raise ValidationError("Phone must be a valid Russian number.")
    return f"+{digits}"


def normalize_vehicle_plate(raw: str) -> str:
    value = " ".join(raw.strip().upper().split())
    if len(value) < 2 or len(value) > 15:
        raise ValidationError("Vehicle plate must be between 2 and 15 characters.")
    if not _PLATE_PATTERN.fullmatch(value):
        raise ValidationError("Vehicle plate contains unsupported characters.")
    return value
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/domain/test_validation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain tests/domain/test_validation.py
git commit -m "feat: add customer input validation"
```

## Task 4: Service Duration Calculation

**Files:**
- Create: `app/domain/services.py`
- Test: `tests/domain/test_services.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/domain/test_services.py`:

```python
import pytest

from app.domain.errors import ValidationError
from app.domain.services import SelectedService, calculate_total_duration


def test_calculate_total_duration_adds_main_service_and_addons() -> None:
    main = SelectedService(id=1, title="Standard", duration_minutes=60, is_addon=False)
    addons = [
        SelectedService(id=2, title="Wax", duration_minutes=15, is_addon=True),
        SelectedService(id=3, title="Tires", duration_minutes=10, is_addon=True),
    ]

    assert calculate_total_duration(main, addons) == 85


def test_calculate_total_duration_rejects_addon_as_main_service() -> None:
    main = SelectedService(id=2, title="Wax", duration_minutes=15, is_addon=True)

    with pytest.raises(ValidationError):
        calculate_total_duration(main, [])


def test_calculate_total_duration_rejects_non_addon_in_addons() -> None:
    main = SelectedService(id=1, title="Standard", duration_minutes=60, is_addon=False)
    addons = [SelectedService(id=4, title="Full", duration_minutes=90, is_addon=False)]

    with pytest.raises(ValidationError):
        calculate_total_duration(main, addons)


def test_calculate_total_duration_rejects_invalid_duration() -> None:
    main = SelectedService(id=1, title="Standard", duration_minutes=0, is_addon=False)

    with pytest.raises(ValidationError):
        calculate_total_duration(main, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_services.py -v
```

Expected: FAIL because `app.domain.services` does not exist.

- [ ] **Step 3: Implement service duration calculation**

Create `app/domain/services.py`:

```python
from dataclasses import dataclass

from app.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class SelectedService:
    id: int
    title: str
    duration_minutes: int
    is_addon: bool


def _validate_duration(duration_minutes: int) -> None:
    if duration_minutes <= 0 or duration_minutes > 480:
        raise ValidationError("Service duration must be between 1 and 480 minutes.")


def calculate_total_duration(main_service: SelectedService, addons: list[SelectedService]) -> int:
    if main_service.is_addon:
        raise ValidationError("Main service cannot be an add-on.")
    _validate_duration(main_service.duration_minutes)

    total = main_service.duration_minutes
    for addon in addons:
        if not addon.is_addon:
            raise ValidationError("Add-on list cannot contain main services.")
        _validate_duration(addon.duration_minutes)
        total += addon.duration_minutes

    if total > 480:
        raise ValidationError("Total booking duration cannot exceed 480 minutes.")
    return total
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/domain/test_services.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/services.py tests/domain/test_services.py
git commit -m "feat: calculate selected service duration"
```

## Task 5: Booking Status Transitions

**Files:**
- Create: `app/domain/statuses.py`
- Test: `tests/domain/test_statuses.py`

- [ ] **Step 1: Write failing status tests**

Create `tests/domain/test_statuses.py`:

```python
import pytest

from app.domain.errors import DomainError
from app.domain.statuses import BookingStatus, ensure_transition_allowed


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BookingStatus.PENDING, BookingStatus.CONFIRMED),
        (BookingStatus.PENDING, BookingStatus.CANCELLED_BY_ADMIN),
        (BookingStatus.PENDING, BookingStatus.CANCELLED_BY_CUSTOMER),
        (BookingStatus.CONFIRMED, BookingStatus.COMPLETED),
        (BookingStatus.CONFIRMED, BookingStatus.NO_SHOW),
        (BookingStatus.CONFIRMED, BookingStatus.CANCELLED_BY_ADMIN),
        (BookingStatus.CONFIRMED, BookingStatus.CANCELLED_BY_CUSTOMER),
    ],
)
def test_allowed_status_transitions(current: BookingStatus, target: BookingStatus) -> None:
    ensure_transition_allowed(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BookingStatus.COMPLETED, BookingStatus.CONFIRMED),
        (BookingStatus.NO_SHOW, BookingStatus.CONFIRMED),
        (BookingStatus.CANCELLED_BY_ADMIN, BookingStatus.CONFIRMED),
        (BookingStatus.CANCELLED_BY_CUSTOMER, BookingStatus.CONFIRMED),
    ],
)
def test_terminal_statuses_cannot_transition(current: BookingStatus, target: BookingStatus) -> None:
    with pytest.raises(DomainError):
        ensure_transition_allowed(current, target)


def test_active_capacity_statuses() -> None:
    assert BookingStatus.PENDING.occupies_capacity is True
    assert BookingStatus.CONFIRMED.occupies_capacity is True
    assert BookingStatus.COMPLETED.occupies_capacity is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_statuses.py -v
```

Expected: FAIL because `app.domain.statuses` does not exist.

- [ ] **Step 3: Implement statuses**

Create `app/domain/statuses.py`:

```python
from enum import StrEnum

from app.domain.errors import DomainError


class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED_BY_CUSTOMER = "cancelled_by_customer"
    CANCELLED_BY_ADMIN = "cancelled_by_admin"
    COMPLETED = "completed"
    NO_SHOW = "no_show"

    @property
    def occupies_capacity(self) -> bool:
        return self in {BookingStatus.PENDING, BookingStatus.CONFIRMED}


_ALLOWED_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.PENDING: {
        BookingStatus.CONFIRMED,
        BookingStatus.CANCELLED_BY_ADMIN,
        BookingStatus.CANCELLED_BY_CUSTOMER,
    },
    BookingStatus.CONFIRMED: {
        BookingStatus.COMPLETED,
        BookingStatus.NO_SHOW,
        BookingStatus.CANCELLED_BY_ADMIN,
        BookingStatus.CANCELLED_BY_CUSTOMER,
    },
    BookingStatus.CANCELLED_BY_CUSTOMER: set(),
    BookingStatus.CANCELLED_BY_ADMIN: set(),
    BookingStatus.COMPLETED: set(),
    BookingStatus.NO_SHOW: set(),
}


def ensure_transition_allowed(current: BookingStatus, target: BookingStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise DomainError(f"Cannot transition booking from {current} to {target}.")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/domain/test_statuses.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/statuses.py tests/domain/test_statuses.py
git commit -m "feat: define booking status transitions"
```

## Task 6: Pure Slot Availability

**Files:**
- Create: `app/domain/time.py`
- Create: `app/domain/slots.py`
- Test: `tests/domain/test_slots.py`

- [ ] **Step 1: Write failing slot tests**

Create `tests/domain/test_slots.py`:

```python
from datetime import datetime, time, timedelta

from app.domain.slots import BookingInterval, BlockedInterval, generate_available_slots


def dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 5, 18, hour, minute)


def test_slot_is_available_when_capacity_remains_for_full_interval() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(9, 0),
        work_end=time(12, 0),
        duration=timedelta(minutes=60),
        slot_step=timedelta(minutes=30),
        bay_count=2,
        bookings=[BookingInterval(start=dt(10), end=dt(11))],
        blocked=[],
    )

    assert dt(10) in slots


def test_slot_is_hidden_when_booking_would_overlap_next_booking_at_full_capacity() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(12, 0),
        work_end=time(14, 0),
        duration=timedelta(minutes=90),
        slot_step=timedelta(minutes=30),
        bay_count=1,
        bookings=[BookingInterval(start=dt(13), end=dt(14))],
        blocked=[],
    )

    assert dt(12) not in slots


def test_slot_is_hidden_when_it_does_not_fit_working_hours() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(9, 0),
        work_end=time(10, 0),
        duration=timedelta(minutes=90),
        slot_step=timedelta(minutes=30),
        bay_count=1,
        bookings=[],
        blocked=[],
    )

    assert slots == []


def test_slot_is_hidden_when_blocked_interval_overlaps() -> None:
    slots = generate_available_slots(
        day=datetime(2026, 5, 18),
        work_start=time(9, 0),
        work_end=time(11, 0),
        duration=timedelta(minutes=30),
        slot_step=timedelta(minutes=30),
        bay_count=1,
        bookings=[],
        blocked=[BlockedInterval(start=dt(9, 30), end=dt(10))],
    )

    assert dt(9, 30) not in slots
    assert dt(10) in slots
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/domain/test_slots.py -v
```

Expected: FAIL because `app.domain.slots` does not exist.

- [ ] **Step 3: Implement slot logic**

Create `app/domain/time.py`:

```python
from datetime import datetime


def intervals_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a
```

Create `app/domain/slots.py`:

```python
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from app.domain.time import intervals_overlap


@dataclass(frozen=True, slots=True)
class BookingInterval:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class BlockedInterval:
    start: datetime
    end: datetime


def generate_available_slots(
    *,
    day: datetime,
    work_start: time,
    work_end: time,
    duration: timedelta,
    slot_step: timedelta,
    bay_count: int,
    bookings: list[BookingInterval],
    blocked: list[BlockedInterval],
) -> list[datetime]:
    work_start_at = datetime.combine(day.date(), work_start)
    work_end_at = datetime.combine(day.date(), work_end)
    slots: list[datetime] = []

    candidate = work_start_at
    while candidate + duration <= work_end_at:
        candidate_end = candidate + duration
        if _fits_capacity(candidate, candidate_end, bay_count, bookings) and _not_blocked(
            candidate, candidate_end, blocked
        ):
            slots.append(candidate)
        candidate += slot_step

    return slots


def _fits_capacity(
    start: datetime,
    end: datetime,
    bay_count: int,
    bookings: list[BookingInterval],
) -> bool:
    overlapping = sum(1 for booking in bookings if intervals_overlap(start, end, booking.start, booking.end))
    return overlapping < bay_count


def _not_blocked(start: datetime, end: datetime, blocked: list[BlockedInterval]) -> bool:
    return not any(intervals_overlap(start, end, item.start, item.end) for item in blocked)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/domain/test_slots.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/time.py app/domain/slots.py tests/domain/test_slots.py
git commit -m "feat: generate available booking slots"
```

## Task 7: Database Models And Migration

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/base.py`
- Create: `app/db/models.py`
- Create: `app/db/session.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`
- Create: `migrations/versions/0001_initial_schema.py`

- [ ] **Step 1: Create SQLAlchemy base and models**

Create `app/db/__init__.py`:

```python
```

Create `app/db/base.py`:

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `app/db/models.py`:

```python
from datetime import datetime, time
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConfirmationMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class ServiceCategory(StrEnum):
    WASH = "wash"
    INTERIOR = "interior"
    ADDON = "addon"


class CarWash(Base):
    __tablename__ = "car_washes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    confirmation_mode: Mapped[str] = mapped_column(String(20), default=ConfirmationMode.AUTO.value)
    reminder_before_minutes: Mapped[int] = mapped_column(Integer, default=60)
    return_visit_delay_days: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    bay_count: Mapped[int] = mapped_column(Integer, nullable=False)

    car_wash: Mapped[CarWash] = relationship()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    vehicle_plate: Mapped[str] = mapped_column(String(15), nullable=False)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_addon: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkingHours(Base):
    __tablename__ = "working_hours"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class BlockedSlot(Base):
    __tablename__ = "blocked_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(nullable=False)
    end_at: Mapped[datetime] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class BookingService(Base):
    __tablename__ = "booking_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False)


class NotificationJob(Base):
    __tablename__ = "notification_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    car_wash_id: Mapped[int] = mapped_column(ForeignKey("car_washes.id"), nullable=False, index=True)
    booking_id: Mapped[int | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(60), nullable=False)
    run_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: Create session helpers**

Create `app/db/session.py`:

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def create_sessionmaker(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def iter_session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as session:
        yield session
```

- [ ] **Step 3: Create Alembic files**

Create `alembic.ini`:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.db import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `migrations/script.py.mako`:

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `migrations/versions/0001_initial_schema.py`:

```python
"""initial schema

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-05-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "car_washes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("confirmation_mode", sa.String(length=20), nullable=False),
        sa.Column("reminder_before_minutes", sa.Integer(), nullable=False),
        sa.Column("return_visit_delay_days", sa.Integer(), nullable=True),
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("bay_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_branches_car_wash_id", "branches", ["car_wash_id"])
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("vehicle_plate", sa.String(length=15), nullable=False),
    )
    op.create_index("ix_customers_car_wash_id", "customers", ["car_wash_id"])
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_admins_car_wash_id", "admins", ["car_wash_id"])
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("is_addon", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_services_car_wash_id", "services", ["car_wash_id"])
    op.create_table(
        "working_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
    )
    op.create_index("ix_working_hours_car_wash_id", "working_hours", ["car_wash_id"])
    op.create_index("ix_working_hours_branch_id", "working_hours", ["branch_id"])
    op.create_table(
        "blocked_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_blocked_slots_car_wash_id", "blocked_slots", ["car_wash_id"])
    op.create_index("ix_blocked_slots_branch_id", "blocked_slots", ["branch_id"])
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_bookings_car_wash_id", "bookings", ["car_wash_id"])
    op.create_index("ix_bookings_branch_id", "bookings", ["branch_id"])
    op.create_index("ix_bookings_start_at", "bookings", ["start_at"])
    op.create_index("ix_bookings_end_at", "bookings", ["end_at"])
    op.create_table(
        "booking_services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("is_main", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_booking_services_booking_id", "booking_services", ["booking_id"])
    op.create_table(
        "notification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_wash_id", sa.Integer(), sa.ForeignKey("car_washes.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=True),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("run_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_index("ix_notification_jobs_car_wash_id", "notification_jobs", ["car_wash_id"])
    op.create_index("ix_notification_jobs_run_at", "notification_jobs", ["run_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_jobs_run_at", table_name="notification_jobs")
    op.drop_index("ix_notification_jobs_car_wash_id", table_name="notification_jobs")
    op.drop_table("notification_jobs")
    op.drop_index("ix_booking_services_booking_id", table_name="booking_services")
    op.drop_table("booking_services")
    op.drop_index("ix_bookings_end_at", table_name="bookings")
    op.drop_index("ix_bookings_start_at", table_name="bookings")
    op.drop_index("ix_bookings_branch_id", table_name="bookings")
    op.drop_index("ix_bookings_car_wash_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_blocked_slots_branch_id", table_name="blocked_slots")
    op.drop_index("ix_blocked_slots_car_wash_id", table_name="blocked_slots")
    op.drop_table("blocked_slots")
    op.drop_index("ix_working_hours_branch_id", table_name="working_hours")
    op.drop_index("ix_working_hours_car_wash_id", table_name="working_hours")
    op.drop_table("working_hours")
    op.drop_index("ix_services_car_wash_id", table_name="services")
    op.drop_table("services")
    op.drop_index("ix_admins_car_wash_id", table_name="admins")
    op.drop_table("admins")
    op.drop_index("ix_customers_car_wash_id", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_branches_car_wash_id", table_name="branches")
    op.drop_table("branches")
    op.drop_table("car_washes")
```

- [ ] **Step 4: Run import check**

Run:

```bash
python -c "from app.db.models import Booking, Service; print(Booking.__tablename__, Service.__tablename__)"
```

Expected output:

```text
bookings services
```

- [ ] **Step 5: Commit**

```bash
git add app/db alembic.ini migrations
git commit -m "feat: add initial database schema"
```

## Task 8: Booking Repository Queries

**Files:**
- Create: `app/db/repositories.py`
- Test: `tests/services/test_booking_service.py`

- [ ] **Step 1: Write repository-facing test skeleton**

Create `tests/services/test_booking_service.py`:

```python
from datetime import datetime

from app.domain.statuses import BookingStatus
from app.services.booking_service import CreateBookingCommand


def test_create_booking_command_keeps_requested_interval() -> None:
    command = CreateBookingCommand(
        car_wash_id=1,
        branch_id=1,
        customer_id=1,
        main_service_id=10,
        addon_service_ids=[11, 12],
        start_at=datetime(2026, 5, 18, 12, 0),
        total_duration_minutes=90,
        confirmation_status=BookingStatus.CONFIRMED,
    )

    assert command.end_at == datetime(2026, 5, 18, 13, 30)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/services/test_booking_service.py -v
```

Expected: FAIL because `app.services.booking_service` does not exist.

- [ ] **Step 3: Implement booking command and repositories**

Create `app/services/__init__.py`:

```python
```

Create `app/services/booking_service.py`:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.statuses import BookingStatus


@dataclass(frozen=True, slots=True)
class CreateBookingCommand:
    car_wash_id: int
    branch_id: int
    customer_id: int
    main_service_id: int
    addon_service_ids: list[int]
    start_at: datetime
    total_duration_minutes: int
    confirmation_status: BookingStatus

    @property
    def end_at(self) -> datetime:
        return self.start_at + timedelta(minutes=self.total_duration_minutes)
```

Create `app/db/repositories.py`:

```python
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BlockedSlot, Booking
from app.domain.statuses import BookingStatus


ACTIVE_CAPACITY_STATUSES = [BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]


def overlapping_bookings_query(
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> Select[tuple[Booking]]:
    return select(Booking).where(
        Booking.car_wash_id == car_wash_id,
        Booking.branch_id == branch_id,
        Booking.status.in_(ACTIVE_CAPACITY_STATUSES),
        Booking.start_at < end_at,
        Booking.end_at > start_at,
    )


def overlapping_blocks_query(
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> Select[tuple[BlockedSlot]]:
    return select(BlockedSlot).where(
        BlockedSlot.car_wash_id == car_wash_id,
        BlockedSlot.branch_id == branch_id,
        BlockedSlot.start_at < end_at,
        BlockedSlot.end_at > start_at,
    )


async def count_overlapping_bookings(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> int:
    result = await session.execute(
        overlapping_bookings_query(
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=start_at,
            end_at=end_at,
        )
    )
    return len(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/services/test_booking_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services app/db/repositories.py tests/services/test_booking_service.py
git commit -m "feat: add booking command and repository queries"
```

## Task 9: Booking Creation Use Case

**Files:**
- Modify: `app/services/booking_service.py`
- Test: `tests/services/test_booking_service.py`

- [ ] **Step 1: Extend failing booking service tests**

Replace `tests/services/test_booking_service.py` with:

```python
from datetime import datetime

import pytest

from app.domain.errors import DomainError
from app.domain.statuses import BookingStatus
from app.services.booking_service import (
    BookingCapacity,
    CreateBookingCommand,
    ensure_booking_can_be_created,
)


def test_create_booking_command_keeps_requested_interval() -> None:
    command = CreateBookingCommand(
        car_wash_id=1,
        branch_id=1,
        customer_id=1,
        main_service_id=10,
        addon_service_ids=[11, 12],
        start_at=datetime(2026, 5, 18, 12, 0),
        total_duration_minutes=90,
        confirmation_status=BookingStatus.CONFIRMED,
    )

    assert command.end_at == datetime(2026, 5, 18, 13, 30)


def test_ensure_booking_can_be_created_allows_remaining_capacity() -> None:
    capacity = BookingCapacity(bay_count=2, overlapping_bookings=1, overlapping_blocks=0)

    ensure_booking_can_be_created(capacity)


def test_ensure_booking_can_be_created_rejects_full_capacity() -> None:
    capacity = BookingCapacity(bay_count=2, overlapping_bookings=2, overlapping_blocks=0)

    with pytest.raises(DomainError):
        ensure_booking_can_be_created(capacity)


def test_ensure_booking_can_be_created_rejects_blocked_time() -> None:
    capacity = BookingCapacity(bay_count=2, overlapping_bookings=0, overlapping_blocks=1)

    with pytest.raises(DomainError):
        ensure_booking_can_be_created(capacity)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/services/test_booking_service.py -v
```

Expected: FAIL because `BookingCapacity` and `ensure_booking_can_be_created` do not exist.

- [ ] **Step 3: Implement booking capacity rules**

Replace `app/services/booking_service.py` with:

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.errors import DomainError, ValidationError
from app.domain.statuses import BookingStatus


@dataclass(frozen=True, slots=True)
class CreateBookingCommand:
    car_wash_id: int
    branch_id: int
    customer_id: int
    main_service_id: int
    addon_service_ids: list[int]
    start_at: datetime
    total_duration_minutes: int
    confirmation_status: BookingStatus

    @property
    def end_at(self) -> datetime:
        if self.total_duration_minutes <= 0:
            raise ValidationError("Booking duration must be positive.")
        return self.start_at + timedelta(minutes=self.total_duration_minutes)


@dataclass(frozen=True, slots=True)
class BookingCapacity:
    bay_count: int
    overlapping_bookings: int
    overlapping_blocks: int


def ensure_booking_can_be_created(capacity: BookingCapacity) -> None:
    if capacity.bay_count <= 0:
        raise ValidationError("Bay count must be positive.")
    if capacity.overlapping_blocks > 0:
        raise DomainError("Selected time is blocked.")
    if capacity.overlapping_bookings >= capacity.bay_count:
        raise DomainError("Selected time has no remaining capacity.")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/services/test_booking_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/booking_service.py tests/services/test_booking_service.py
git commit -m "feat: validate booking creation capacity"
```

## Task 10: Quality Gate

**Files:**
- Modify only files needed to fix issues found by verification.

- [ ] **Step 1: Run full tests**

Run:

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run lint**

Run:

```bash
ruff check .
```

Expected: no errors.

- [ ] **Step 3: Run format check**

Run:

```bash
ruff format --check .
```

Expected: no formatting changes needed.

- [ ] **Step 4: Run type check**

Run:

```bash
mypy app
```

Expected: no type errors.

- [ ] **Step 5: Commit verification fixes if any**

If any command required fixes:

```bash
git add .
git commit -m "chore: pass foundation quality gate"
```

If no files changed, do not create an empty commit.

## Self-Review

Spec coverage in this plan:

- Modular monolith structure: covered by Tasks 1, 2, 7, and 8.
- Input validation: covered by Task 3.
- Service/add-on duration calculation: covered by Task 4.
- Status rules: covered by Task 5.
- Full-interval slot availability: covered by Task 6.
- Database foundation: covered by Task 7.
- Booking capacity guard: covered by Tasks 8 and 9.
- TDD and quality gate: covered throughout and Task 10.

Intentional gaps for later plans:

- Telegram bot customer flow.
- Telegram admin flow.
- Notification worker and retry behavior.
- FastAPI endpoints.
- Docker Compose deployment.
- Acceptance smoke flow through Telegram.

Placeholder scan:

- The plan contains no unfinished implementation placeholders.
- Follow-up subsystems are explicitly out of scope, not placeholders inside this plan.

Type consistency:

- `BookingStatus`, `CreateBookingCommand`, `BookingCapacity`, `SelectedService`, `BookingInterval`, and `BlockedInterval` are defined before use.
- File paths in tasks match the file structure section.
