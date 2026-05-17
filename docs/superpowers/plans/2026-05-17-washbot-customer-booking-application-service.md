# WashBot Customer Booking Application Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend application service that a Telegram customer booking flow can call to list services, show available slots, and create bookings transactionally.

**Architecture:** Keep Telegram out of this slice. Add a service layer that orchestrates existing domain rules and SQLAlchemy repositories. Repositories return simple DTOs/intervals; domain code remains DB-free; the application service performs validation and transaction-safe booking creation.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x async sessions, pytest, pytest-asyncio, aiosqlite for async DB tests, Ruff, mypy.

---

## Scope Notes

This plan does not implement aiogram handlers, keyboards, admin flows, notification delivery, or Docker deployment. It creates the backend use-cases the Telegram bot will call next.

The slice produces working, testable software:

- service menu from DB;
- available slot generation from DB data;
- booking creation with repeated availability check;
- customer persistence;
- booking services persistence;
- reminder notification job creation.

## File Structure

Create or modify:

- `pyproject.toml`: add `aiosqlite` to dev dependencies for async SQLite tests.
- `app/domain/slots.py`: expose peak occupancy helper for booking creation.
- `app/db/repositories.py`: add focused read/write helpers for branches, services, customers, bookings, working hours, blocks, and notification jobs.
- `app/services/customer_booking.py`: application service DTOs and use-cases.
- `tests/conftest.py`: async SQLite database/session fixtures.
- `tests/domain/test_slots.py`: regression tests for public peak occupancy helper.
- `tests/db/test_booking_repositories.py`: repository integration tests.
- `tests/services/test_customer_booking.py`: application service integration tests.

## Task 1: Async DB Test Harness

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/conftest.py`
- Test: `tests/db/test_db_harness.py`

- [ ] **Step 1: Write failing DB harness test**

Create `tests/db/test_db_harness.py`:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CarWash


async def test_async_db_session_fixture_persists_rows(db_session: AsyncSession) -> None:
    db_session.add(CarWash(name="Test wash"))
    await db_session.commit()

    result = await db_session.execute(select(CarWash.name))

    assert result.scalar_one() == "Test wash"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/db/test_db_harness.py -v
```

Expected: FAIL because `db_session` fixture does not exist, or because `aiosqlite` is not installed.

- [ ] **Step 3: Add aiosqlite dev dependency**

Modify `pyproject.toml` dev dependencies:

```toml
dev = [
    "aiosqlite>=0.20,<1",
    "httpx>=0.27,<1",
    "mypy>=1.10,<2",
    "pytest>=8.2,<9",
    "pytest-asyncio>=0.23,<1",
    "ruff>=0.4,<1",
]
```

- [ ] **Step 4: Install updated dev dependencies**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pip install -e ".[dev]"
```

Expected: install succeeds and includes `aiosqlite`.

- [ ] **Step 5: Add async DB fixtures**

Create `tests/conftest.py`:

```python
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session

    await engine.dispose()
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/db/test_db_harness.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml tests/conftest.py tests/db/test_db_harness.py
git commit -m "test: add async database test harness"
```

## Task 2: Public Peak Occupancy Helper

**Files:**
- Modify: `app/domain/slots.py`
- Modify: `tests/domain/test_slots.py`

- [ ] **Step 1: Write failing peak occupancy tests**

Append to `tests/domain/test_slots.py`:

```python
from app.domain.slots import calculate_peak_occupancy


def test_calculate_peak_occupancy_counts_sequential_bookings_as_one_peak() -> None:
    peak = calculate_peak_occupancy(
        start=dt(10),
        end=dt(12),
        bookings=[
            BookingInterval(start=dt(10), end=dt(11)),
            BookingInterval(start=dt(11), end=dt(12)),
        ],
    )

    assert peak == 1


def test_calculate_peak_occupancy_counts_concurrent_bookings_as_two_peak() -> None:
    peak = calculate_peak_occupancy(
        start=dt(10),
        end=dt(12),
        bookings=[
            BookingInterval(start=dt(10), end=dt(12)),
            BookingInterval(start=dt(10, 30), end=dt(11, 30)),
        ],
    )

    assert peak == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/domain/test_slots.py -v
```

Expected: FAIL because `calculate_peak_occupancy` is not exported yet.

- [ ] **Step 3: Expose helper in domain slots**

Modify `app/domain/slots.py` so `_fits_capacity` uses this public helper:

```python
def calculate_peak_occupancy(
    *,
    start: datetime,
    end: datetime,
    bookings: list[BookingInterval],
) -> int:
    events: list[tuple[datetime, int]] = []
    for booking in bookings:
        if not intervals_overlap(start, end, booking.start, booking.end):
            continue
        events.append((max(start, booking.start), 1))
        events.append((min(end, booking.end), -1))

    occupied = 0
    peak = 0
    for _, delta in sorted(events, key=lambda event: (event[0], event[1])):
        occupied += delta
        peak = max(peak, occupied)

    return peak
```

Then implement `_fits_capacity` as:

```python
def _fits_capacity(
    start: datetime,
    end: datetime,
    bay_count: int,
    bookings: list[BookingInterval],
) -> bool:
    return calculate_peak_occupancy(start=start, end=end, bookings=bookings) < bay_count
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/domain/test_slots.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/domain/slots.py tests/domain/test_slots.py
git commit -m "feat: expose peak occupancy helper"
```

## Task 3: Booking Repository Read Helpers

**Files:**
- Modify: `app/db/repositories.py`
- Test: `tests/db/test_booking_repositories.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/db/test_booking_repositories.py`:

```python
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, CarWash, Service, WorkingHours
from app.db.repositories import (
    get_branch,
    get_working_hours_for_weekday,
    list_active_addon_services,
    list_active_main_services,
)


async def test_service_repositories_split_main_services_and_addons(db_session: AsyncSession) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    db_session.add_all(
        [
            Service(
                car_wash_id=car_wash.id,
                title="Body wash",
                category="wash",
                price=Decimal("500"),
                duration_minutes=30,
                is_addon=False,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Wax",
                category="addon",
                price=Decimal("200"),
                duration_minutes=15,
                is_addon=True,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Old package",
                category="wash",
                price=Decimal("1000"),
                duration_minutes=60,
                is_addon=False,
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    main_services = await list_active_main_services(db_session, car_wash_id=car_wash.id)
    addons = await list_active_addon_services(db_session, car_wash_id=car_wash.id)

    assert [service.title for service in main_services] == ["Body wash"]
    assert [service.title for service in addons] == ["Wax"]


async def test_branch_and_working_hours_repositories_return_config(db_session: AsyncSession) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(
        car_wash_id=car_wash.id,
        title="Main",
        address="Street",
        bay_count=2,
    )
    db_session.add(branch)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(9),
            end_time=time(18),
        )
    )
    await db_session.commit()

    loaded_branch = await get_branch(db_session, car_wash_id=car_wash.id, branch_id=branch.id)
    hours = await get_working_hours_for_weekday(
        db_session,
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        weekday=0,
    )

    assert loaded_branch is not None
    assert loaded_branch.bay_count == 2
    assert hours is not None
    assert hours.start_time == time(9)
    assert hours.end_time == time(18)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/db/test_booking_repositories.py -v
```

Expected: FAIL because repository helpers do not exist.

- [ ] **Step 3: Implement read helpers**

Append to `app/db/repositories.py`:

```python
from app.db.models import Branch, Service, WorkingHours


async def list_active_main_services(session: AsyncSession, *, car_wash_id: int) -> list[Service]:
    result = await session.execute(
        select(Service)
        .where(
            Service.car_wash_id == car_wash_id,
            Service.is_active.is_(True),
            Service.is_addon.is_(False),
        )
        .order_by(Service.id)
    )
    return list(result.scalars().all())


async def list_active_addon_services(session: AsyncSession, *, car_wash_id: int) -> list[Service]:
    result = await session.execute(
        select(Service)
        .where(
            Service.car_wash_id == car_wash_id,
            Service.is_active.is_(True),
            Service.is_addon.is_(True),
        )
        .order_by(Service.id)
    )
    return list(result.scalars().all())


async def get_branch(session: AsyncSession, *, car_wash_id: int, branch_id: int) -> Branch | None:
    result = await session.execute(
        select(Branch).where(Branch.car_wash_id == car_wash_id, Branch.id == branch_id)
    )
    return result.scalar_one_or_none()


async def get_working_hours_for_weekday(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    weekday: int,
) -> WorkingHours | None:
    result = await session.execute(
        select(WorkingHours).where(
            WorkingHours.car_wash_id == car_wash_id,
            WorkingHours.branch_id == branch_id,
            WorkingHours.weekday == weekday,
        )
    )
    return result.scalar_one_or_none()
```

If imports become duplicated, merge them cleanly at the top of `app/db/repositories.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/db/test_booking_repositories.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/db/repositories.py tests/db/test_booking_repositories.py
git commit -m "feat: add booking read repositories"
```

## Task 4: Customer Booking Service Menu

**Files:**
- Create: `app/services/customer_booking.py`
- Test: `tests/services/test_customer_booking.py`

- [ ] **Step 1: Write failing menu test**

Create `tests/services/test_customer_booking.py`:

```python
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CarWash, Service
from app.services.customer_booking import CustomerBookingService


async def test_get_service_menu_returns_main_services_and_addons(db_session: AsyncSession) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    db_session.add_all(
        [
            Service(
                car_wash_id=car_wash.id,
                title="Standard",
                category="wash",
                price=Decimal("900"),
                duration_minutes=60,
                is_addon=False,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Wax",
                category="addon",
                price=Decimal("250"),
                duration_minutes=15,
                is_addon=True,
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    menu = await CustomerBookingService(db_session).get_service_menu(car_wash_id=car_wash.id)

    assert [service.title for service in menu.main_services] == ["Standard"]
    assert [service.title for service in menu.addons] == ["Wax"]
    assert menu.main_services[0].price == Decimal("900")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py -v
```

Expected: FAIL because `app.services.customer_booking` does not exist.

- [ ] **Step 3: Implement service menu DTOs**

Create `app/services/customer_booking.py`:

```python
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.db.models import Service


@dataclass(frozen=True, slots=True)
class ServiceOption:
    id: int
    title: str
    category: str
    price: Decimal
    duration_minutes: int
    is_addon: bool


@dataclass(frozen=True, slots=True)
class ServiceMenu:
    main_services: list[ServiceOption]
    addons: list[ServiceOption]


def _to_service_option(service: Service) -> ServiceOption:
    return ServiceOption(
        id=service.id,
        title=service.title,
        category=service.category,
        price=service.price,
        duration_minutes=service.duration_minutes,
        is_addon=service.is_addon,
    )


class CustomerBookingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_service_menu(self, *, car_wash_id: int) -> ServiceMenu:
        main_services = await repositories.list_active_main_services(
            self._session,
            car_wash_id=car_wash_id,
        )
        addons = await repositories.list_active_addon_services(
            self._session,
            car_wash_id=car_wash_id,
        )
        return ServiceMenu(
            main_services=[_to_service_option(service) for service in main_services],
            addons=[_to_service_option(service) for service in addons],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/customer_booking.py tests/services/test_customer_booking.py
git commit -m "feat: add customer service menu use case"
```

## Task 5: Available Slots Use Case

**Files:**
- Modify: `app/db/repositories.py`
- Modify: `app/services/customer_booking.py`
- Modify: `tests/services/test_customer_booking.py`

- [ ] **Step 1: Write failing available slots tests**

Append to `tests/services/test_customer_booking.py`:

```python
from datetime import date, datetime, time

from app.db.models import Booking, Branch, WorkingHours


async def test_get_available_slots_uses_services_working_hours_and_capacity(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    db_session.add(branch)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=120,
        is_addon=False,
        is_active=True,
    )
    db_session.add(main_service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    db_session.add_all(
        [
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 10),
                end_at=datetime(2026, 5, 18, 11),
                status="confirmed",
            ),
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 11),
                end_at=datetime(2026, 5, 18, 12),
                status="confirmed",
            ),
        ]
    )
    await db_session.commit()

    slots = await CustomerBookingService(db_session).get_available_slots(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[main_service.id],
        day=date(2026, 5, 18),
    )

    assert slots == [datetime(2026, 5, 18, 10)]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py::test_get_available_slots_uses_services_working_hours_and_capacity -v
```

Expected: FAIL because `get_available_slots` does not exist.

- [ ] **Step 3: Add repository helper to fetch services by ids**

Append to `app/db/repositories.py`:

```python
async def list_services_by_ids(
    session: AsyncSession,
    *,
    car_wash_id: int,
    service_ids: list[int],
) -> list[Service]:
    if not service_ids:
        return []
    result = await session.execute(
        select(Service)
        .where(
            Service.car_wash_id == car_wash_id,
            Service.id.in_(service_ids),
            Service.is_active.is_(True),
        )
        .order_by(Service.id)
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: Implement available slots use case**

Extend imports in `app/services/customer_booking.py`:

```python
from app.domain.errors import DomainError
from app.domain.services import SelectedService, calculate_total_duration
from app.domain.slots import BlockedInterval, BookingInterval, generate_available_slots
```

Add helper:

```python
def _selected_service_from_model(service: Service) -> SelectedService:
    return SelectedService(
        id=service.id,
        title=service.title,
        duration_minutes=service.duration_minutes,
        is_addon=service.is_addon,
    )
```

Add method to `CustomerBookingService`:

```python
    async def get_available_slots(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        selected_service_ids: list[int],
        day: date,
    ) -> list[datetime]:
        branch = await repositories.get_branch(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
        )
        if branch is None:
            raise DomainError("Branch was not found.")

        hours = await repositories.get_working_hours_for_weekday(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            weekday=day.weekday(),
        )
        if hours is None:
            return []

        services = await repositories.list_services_by_ids(
            self._session,
            car_wash_id=car_wash_id,
            service_ids=selected_service_ids,
        )
        if len(services) != len(set(selected_service_ids)):
            raise DomainError("One or more services were not found.")

        main_services = [service for service in services if not service.is_addon]
        addons = [service for service in services if service.is_addon]
        if len(main_services) != 1:
            raise DomainError("Exactly one main service is required.")

        duration = calculate_total_duration(
            _selected_service_from_model(main_services[0]),
            [_selected_service_from_model(service) for service in addons],
        )
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day, time.max)
        booking_intervals = await repositories.list_overlapping_booking_intervals(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=day_start,
            end_at=day_end,
        )
        block_result = await self._session.execute(
            repositories.overlapping_blocks_query(
                car_wash_id=car_wash_id,
                branch_id=branch_id,
                start_at=day_start,
                end_at=day_end,
            )
        )
        blocks = list(block_result.scalars().all())

        return generate_available_slots(
            day=datetime.combine(day, time.min),
            work_start=hours.start_time,
            work_end=hours.end_time,
            duration=timedelta(minutes=duration),
            slot_step=timedelta(minutes=30),
            bay_count=branch.bay_count,
            bookings=[
                BookingInterval(start=start_at, end=end_at)
                for start_at, end_at in booking_intervals
            ],
            blocked=[
                BlockedInterval(start=blocked.start_at, end=blocked.end_at)
                for blocked in blocks
            ],
        )
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db/repositories.py app/services/customer_booking.py tests/services/test_customer_booking.py
git commit -m "feat: add available slots use case"
```

## Task 6: Booking Creation Persistence

**Files:**
- Modify: `app/db/repositories.py`
- Modify: `app/services/customer_booking.py`
- Modify: `tests/services/test_customer_booking.py`

- [ ] **Step 1: Write failing booking creation test**

Append to `tests/services/test_customer_booking.py`:

```python
from sqlalchemy import select

from app.db.models import BookingService, Customer, NotificationJob


async def test_create_booking_persists_customer_booking_services_and_reminder(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(main_service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[main_service.id],
        start_at=datetime(2026, 5, 18, 10),
        customer_name=" Иван ",
        customer_phone="8 (913) 123-45-67",
        vehicle_plate="а123вс154",
    )

    customers = (await db_session.execute(select(Customer))).scalars().all()
    booking_services = (await db_session.execute(select(BookingService))).scalars().all()
    jobs = (await db_session.execute(select(NotificationJob))).scalars().all()

    assert booking.status == "confirmed"
    assert booking.end_at == datetime(2026, 5, 18, 11)
    assert customers[0].name == "Иван"
    assert customers[0].phone == "+79131234567"
    assert customers[0].vehicle_plate == "А123ВС154"
    assert len(booking_services) == 1
    assert jobs[0].kind == "booking_reminder"
    assert jobs[0].run_at == datetime(2026, 5, 18, 9)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py::test_create_booking_persists_customer_booking_services_and_reminder -v
```

Expected: FAIL because `create_booking` does not exist.

- [ ] **Step 3: Add write repositories**

Append to `app/db/repositories.py`:

```python
from app.db.models import BookingService as BookingServiceModel
from app.db.models import Customer, NotificationJob


async def get_car_wash(session: AsyncSession, *, car_wash_id: int) -> CarWash | None:
    result = await session.execute(select(CarWash).where(CarWash.id == car_wash_id))
    return result.scalar_one_or_none()


async def create_customer(
    session: AsyncSession,
    *,
    car_wash_id: int,
    name: str,
    phone: str,
    vehicle_plate: str,
) -> Customer:
    customer = Customer(
        car_wash_id=car_wash_id,
        name=name,
        phone=phone,
        vehicle_plate=vehicle_plate,
    )
    session.add(customer)
    await session.flush()
    return customer


async def create_booking_record(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    customer_id: int,
    start_at: datetime,
    end_at: datetime,
    status: str,
) -> Booking:
    booking = Booking(
        car_wash_id=car_wash_id,
        branch_id=branch_id,
        customer_id=customer_id,
        start_at=start_at,
        end_at=end_at,
        status=status,
    )
    session.add(booking)
    await session.flush()
    return booking


async def add_booking_services(
    session: AsyncSession,
    *,
    booking_id: int,
    main_service_id: int,
    addon_service_ids: list[int],
) -> None:
    session.add(BookingServiceModel(booking_id=booking_id, service_id=main_service_id, is_main=True))
    session.add_all(
        [
            BookingServiceModel(booking_id=booking_id, service_id=service_id, is_main=False)
            for service_id in addon_service_ids
        ]
    )
    await session.flush()


async def create_notification_job(
    session: AsyncSession,
    *,
    car_wash_id: int,
    booking_id: int,
    kind: str,
    run_at: datetime,
) -> NotificationJob:
    job = NotificationJob(
        car_wash_id=car_wash_id,
        booking_id=booking_id,
        kind=kind,
        run_at=run_at,
        status="pending",
        attempts=0,
    )
    session.add(job)
    await session.flush()
    return job
```

Merge imports at the top of the file so `CarWash`, `BookingServiceModel`, `Customer`, and `NotificationJob` are imported once.

- [ ] **Step 4: Implement create_booking use case**

Extend imports in `app/services/customer_booking.py`:

```python
from app.domain.slots import calculate_peak_occupancy
from app.domain.statuses import BookingStatus
from app.domain.validation import normalize_name, normalize_phone, normalize_vehicle_plate
from app.services.booking_service import BookingCapacity, ensure_booking_can_be_created
```

Add method:

```python
    async def create_booking(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        selected_service_ids: list[int],
        start_at: datetime,
        customer_name: str,
        customer_phone: str,
        vehicle_plate: str,
    ):
        car_wash = await repositories.get_car_wash(self._session, car_wash_id=car_wash_id)
        if car_wash is None:
            raise DomainError("Car wash was not found.")

        branch = await repositories.get_branch(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
        )
        if branch is None:
            raise DomainError("Branch was not found.")

        services = await repositories.list_services_by_ids(
            self._session,
            car_wash_id=car_wash_id,
            service_ids=selected_service_ids,
        )
        if len(services) != len(set(selected_service_ids)):
            raise DomainError("One or more services were not found.")

        main_services = [service for service in services if not service.is_addon]
        addons = [service for service in services if service.is_addon]
        if len(main_services) != 1:
            raise DomainError("Exactly one main service is required.")

        duration = calculate_total_duration(
            _selected_service_from_model(main_services[0]),
            [_selected_service_from_model(service) for service in addons],
        )
        end_at = start_at + timedelta(minutes=duration)

        block_result = await self._session.execute(
            repositories.overlapping_blocks_query(
                car_wash_id=car_wash_id,
                branch_id=branch_id,
                start_at=start_at,
                end_at=end_at,
            )
        )
        overlapping_blocks = len(block_result.scalars().all())
        booking_intervals = await repositories.list_overlapping_booking_intervals(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=start_at,
            end_at=end_at,
        )
        peak_occupied_bays = calculate_peak_occupancy(
            start=start_at,
            end=end_at,
            bookings=[
                BookingInterval(start=interval_start, end=interval_end)
                for interval_start, interval_end in booking_intervals
            ],
        )
        ensure_booking_can_be_created(
            BookingCapacity(
                bay_count=branch.bay_count,
                peak_occupied_bays=peak_occupied_bays,
                overlapping_blocks=overlapping_blocks,
            )
        )

        customer = await repositories.create_customer(
            self._session,
            car_wash_id=car_wash_id,
            name=normalize_name(customer_name),
            phone=normalize_phone(customer_phone),
            vehicle_plate=normalize_vehicle_plate(vehicle_plate),
        )
        status = (
            BookingStatus.CONFIRMED
            if car_wash.confirmation_mode == "auto"
            else BookingStatus.PENDING
        )
        booking = await repositories.create_booking_record(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            customer_id=customer.id,
            start_at=start_at,
            end_at=end_at,
            status=status.value,
        )
        await repositories.add_booking_services(
            self._session,
            booking_id=booking.id,
            main_service_id=main_services[0].id,
            addon_service_ids=[service.id for service in addons],
        )
        reminder_at = start_at - timedelta(minutes=car_wash.reminder_before_minutes)
        if reminder_at >= datetime.now().replace(microsecond=0):
            await repositories.create_notification_job(
                self._session,
                car_wash_id=car_wash_id,
                booking_id=booking.id,
                kind="booking_reminder",
                run_at=reminder_at,
            )
        await self._session.commit()
        return booking
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db/repositories.py app/services/customer_booking.py tests/services/test_customer_booking.py
git commit -m "feat: create customer booking use case"
```

## Task 7: Booking Creation Regression Tests

**Files:**
- Modify: `tests/services/test_customer_booking.py`
- Modify: `app/services/customer_booking.py` only if tests reveal a bug.

- [ ] **Step 1: Add regression tests**

Append to `tests/services/test_customer_booking.py`:

```python
import pytest

from app.domain.errors import DomainError


async def test_create_booking_rejects_slot_when_capacity_is_full(db_session: AsyncSession) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
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
    db_session.add(
        Booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            customer_id=1,
            start_at=datetime(2026, 5, 18, 10),
            end_at=datetime(2026, 5, 18, 11),
            status="confirmed",
        )
    )
    await db_session.commit()

    with pytest.raises(DomainError):
        await CustomerBookingService(db_session).create_booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            selected_service_ids=[service.id],
            start_at=datetime(2026, 5, 18, 10),
            customer_name="Ivan",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
        )


async def test_create_booking_allows_sequential_existing_bookings_with_free_peak_capacity(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    db_session.add(branch)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Long package",
        category="wash",
        price=Decimal("1500"),
        duration_minutes=120,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    db_session.add_all(
        [
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 10),
                end_at=datetime(2026, 5, 18, 11),
                status="confirmed",
            ),
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 11),
                end_at=datetime(2026, 5, 18, 12),
                status="confirmed",
            ),
        ]
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[service.id],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
    )

    assert booking.start_at == datetime(2026, 5, 18, 10)
    assert booking.end_at == datetime(2026, 5, 18, 12)
```

- [ ] **Step 2: Run regression tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py -v
```

Expected: PASS. If a test fails, fix `app/services/customer_booking.py` minimally and rerun.

- [ ] **Step 3: Commit**

```bash
git add tests/services/test_customer_booking.py app/services/customer_booking.py
git commit -m "test: cover customer booking capacity regressions"
```

## Task 8: Quality Gate

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
git commit -m "chore: pass customer booking quality gate"
```

If no files changed, do not create an empty commit.

## Self-Review

Spec coverage:

- Service menu from active services: Task 4.
- Slot availability from selected services, working hours, blocked slots, active booking intervals, and bay capacity: Task 5.
- Transaction-style booking creation with repeated availability check inputs: Task 6.
- Customer name, phone, and vehicle plate normalization: Task 6.
- Auto/manual confirmation status: Task 6.
- Reminder notification job creation: Task 6.
- Regression around peak occupancy instead of row count: Tasks 5 and 7.

Intentional gaps:

- Telegram handlers/keyboards/FSM are not implemented in this plan.
- Admin operations are not implemented in this plan.
- Notification worker delivery/retry is not implemented in this plan.
- Docker deployment is not implemented in this plan.

Placeholder scan:

- The plan contains no unfinished implementation placeholders.
- Deferred subsystems are explicit out-of-scope items.

Type consistency:

- `ServiceOption`, `ServiceMenu`, and `CustomerBookingService` are defined before use.
- Repository helper names used by service methods are defined in earlier tasks.
- Capacity semantics stay peak-based through `calculate_peak_occupancy` and `BookingCapacity.peak_occupied_bays`.

