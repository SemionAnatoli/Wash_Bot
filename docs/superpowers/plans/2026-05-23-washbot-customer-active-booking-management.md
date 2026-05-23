# WashBot Customer Active Booking Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a Telegram customer view their one active future booking and cancel it when at least 60 minutes remain before start.

**Architecture:** Keep Telegram handlers thin over `CustomerBookingService`. Store the Telegram user link on `Customer.user_id` when booking is created, then load/cancel the active booking through repository helpers. Reuse existing callback/message/keyboard modules and keep dynamic text HTML-safe.

**Tech Stack:** Python 3.12, aiogram 3.13.1, SQLAlchemy async ORM, pytest, Ruff, mypy.

---

## Scope Notes

This plan builds customer self-service for one active booking.

It does not implement admin cancellation, rescheduling, admin notifications, or multiple active booking selection.

Cancellation boundary:

- exactly 60 minutes before booking start is allowed;
- less than 60 minutes before booking start is denied.

## File Structure

Create or modify:

- `app/domain/errors.py`: add `CancellationTooLateError`.
- `app/db/repositories.py`: add Telegram user/customer helpers, active booking query, selected service query, and booking status update helper.
- `app/services/customer_booking.py`: add active-booking DTOs, associate created bookings with Telegram users, load active booking, cancel active booking.
- `app/bot/customer_booking/callbacks.py`: add active-booking callback constants.
- `app/bot/customer_booking/messages.py`: add active-booking texts and summary formatter.
- `app/bot/customer_booking/keyboards.py`: add entry/cancel active booking buttons.
- `app/bot/customer_booking/handlers.py`: pass Telegram user data into booking creation, add “my booking” and cancel handlers, register callbacks.
- `tests/services/test_customer_booking.py`: service coverage for active booking and cancellation rules.
- `tests/bot/customer_booking/test_callbacks.py`: callback constants coverage.
- `tests/bot/customer_booking/test_messages.py`: summary and HTML escaping coverage.
- `tests/bot/customer_booking/test_keyboards.py`: keyboard coverage.
- `tests/bot/customer_booking/fakes.py`: fake Telegram user and active-booking fake service behavior.
- `tests/bot/customer_booking/test_handlers.py`: handler coverage.

## Task 1: Active Booking Callback, Message, And Keyboard Helpers

**Files:**
- Modify: `app/bot/customer_booking/callbacks.py`
- Modify: `app/bot/customer_booking/messages.py`
- Modify: `app/bot/customer_booking/keyboards.py`
- Test: `tests/bot/customer_booking/test_callbacks.py`
- Test: `tests/bot/customer_booking/test_messages.py`
- Test: `tests/bot/customer_booking/test_keyboards.py`

- [ ] **Step 1: Write failing callback tests**

Append to `tests/bot/customer_booking/test_callbacks.py`:

```python
from app.bot.customer_booking.callbacks import (
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
)


def test_active_booking_callbacks_are_stable() -> None:
    assert MY_ACTIVE_BOOKING_CALLBACK == "book:my_active"
    assert CANCEL_ACTIVE_BOOKING_CALLBACK == "book:cancel_active"
```

- [ ] **Step 2: Write failing message tests**

Append to `tests/bot/customer_booking/test_messages.py`:

```python
from app.bot.customer_booking.messages import (
    ACTIVE_BOOKING_EMPTY_TEXT,
    ACTIVE_BOOKING_CANCELLED_TEXT,
    ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT,
    format_active_booking_summary,
)
from app.services.customer_booking import ActiveCustomerBooking


def test_active_booking_text_constants_are_user_facing() -> None:
    assert ACTIVE_BOOKING_EMPTY_TEXT == "У вас нет активной записи."
    assert ACTIVE_BOOKING_CANCELLED_TEXT == "Запись отменена."
    assert (
        ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT
        == "Отменить запись уже нельзя. Свяжитесь с администратором."
    )


def test_format_active_booking_summary_contains_booking_details() -> None:
    text = format_active_booking_summary(
        ActiveCustomerBooking(
            booking_id=15,
            status="confirmed",
            start_at=datetime(2026, 5, 18, 10),
            end_at=datetime(2026, 5, 18, 11, 15),
            customer_name="Иван",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
            services=[
                option(1, "Стандарт", "900", 60),
                option(2, "Воск", "250", 15, is_addon=True),
            ],
        )
    )

    assert "Ваша запись" in text
    assert "18.05.2026 10:00" in text
    assert "Подтверждена" in text
    assert "A123BC154" in text
    assert "Стандарт" in text
    assert "Воск" in text
    assert "1 ч 15 мин" in text
    assert "1150 руб." in text


def test_format_active_booking_summary_escapes_html_dynamic_fields() -> None:
    text = format_active_booking_summary(
        ActiveCustomerBooking(
            booking_id=15,
            status="pending",
            start_at=datetime(2026, 5, 18, 10),
            end_at=datetime(2026, 5, 18, 10, 30),
            customer_name="A < B",
            customer_phone="+7&913",
            vehicle_plate="A<123>",
            services=[option(1, "Wash <Pro> & Wax", "100", 30)],
        )
    )

    assert "A &lt; B" in text
    assert "+7&amp;913" in text
    assert "A&lt;123&gt;" in text
    assert "Wash &lt;Pro&gt; &amp; Wax" in text
```

- [ ] **Step 3: Write failing keyboard tests**

Modify `tests/bot/customer_booking/test_keyboards.py` imports:

```python
from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
)
from app.bot.customer_booking.keyboards import (
    active_booking_keyboard,
    addons_keyboard,
    booking_entry_keyboard,
    confirmation_keyboard,
    date_keyboard,
    main_services_keyboard,
    no_slots_keyboard,
    slots_keyboard,
)
```

Replace `test_booking_entry_keyboard_contains_start_action` with:

```python
def test_booking_entry_keyboard_contains_start_and_active_booking_actions() -> None:
    markup = booking_entry_keyboard()

    assert callback_grid(markup) == [[BOOKING_START_CALLBACK], [MY_ACTIVE_BOOKING_CALLBACK]]
    assert text_grid(markup) == [["Записаться"], ["Моя запись"]]
```

Append:

```python
def test_active_booking_keyboard_contains_cancel_action() -> None:
    markup = active_booking_keyboard()

    assert callback_grid(markup) == [[CANCEL_ACTIVE_BOOKING_CALLBACK]]
    assert text_grid(markup) == [["Отменить запись"]]
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_callbacks.py tests/bot/customer_booking/test_messages.py tests/bot/customer_booking/test_keyboards.py -q
```

Expected: FAIL because constants, formatter, and keyboard do not exist.

- [ ] **Step 5: Add callback constants**

Modify `app/bot/customer_booking/callbacks.py`:

```python
MY_ACTIVE_BOOKING_CALLBACK = "book:my_active"
CANCEL_ACTIVE_BOOKING_CALLBACK = "book:cancel_active"
```

- [ ] **Step 6: Add active booking texts and formatter**

Modify `app/bot/customer_booking/messages.py`:

```python
from html import escape
```

Add constants:

```python
ACTIVE_BOOKING_EMPTY_TEXT = "У вас нет активной записи."
ACTIVE_BOOKING_CANCELLED_TEXT = "Запись отменена."
ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT = (
    "Отменить запись уже нельзя. Свяжитесь с администратором."
)
```

Add helpers:

```python
def _status_label(status: str) -> str:
    labels = {
        "pending": "Ожидает подтверждения",
        "confirmed": "Подтверждена",
    }
    return labels.get(status, status)


def format_active_booking_summary(booking: ActiveCustomerBooking) -> str:
    total_price = sum((service.price for service in booking.services), Decimal("0"))
    total_duration = sum(service.duration_minutes for service in booking.services)
    service_lines = "\n".join(f"- {service_line(service)}" for service in booking.services)
    return (
        "Ваша запись:\n\n"
        f"Дата и время: {booking.start_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: {escape(_status_label(booking.status))}\n"
        f"Авто: {escape(booking.vehicle_plate)}\n"
        f"Услуги:\n{service_lines}\n"
        f"Длительность: {format_duration(total_duration)}\n"
        f"Итого: {format_money(total_price)}\n\n"
        f"Имя: {escape(booking.customer_name)}\n"
        f"Телефон: {escape(booking.customer_phone)}"
    )
```

Also ensure `service_line()` escapes service titles:

```python
def service_line(service: ServiceOption) -> str:
    return (
        f"{escape(service.title)} — {format_money(service.price)}, "
        f"{format_duration(service.duration_minutes)}"
    )
```

Add this import guarded by runtime type need:

```python
from app.services.customer_booking import ActiveCustomerBooking, ServiceOption
```

- [ ] **Step 7: Add keyboards**

Modify `app/bot/customer_booking/keyboards.py` imports:

```python
from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CHANGE_TIME_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
    build_addon_callback,
    build_date_callback,
    build_main_service_callback,
    build_slot_callback,
)
```

Replace `booking_entry_keyboard()` with:

```python
def booking_entry_keyboard() -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text="Записаться",
                    callback_data=BOOKING_START_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="Моя запись",
                    callback_data=MY_ACTIVE_BOOKING_CALLBACK,
                )
            ],
        ]
    )
```

Add:

```python
def active_booking_keyboard() -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text="Отменить запись",
                    callback_data=CANCEL_ACTIVE_BOOKING_CALLBACK,
                )
            ]
        ]
    )
```

- [ ] **Step 8: Run helper tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_callbacks.py tests/bot/customer_booking/test_messages.py tests/bot/customer_booking/test_keyboards.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/bot/customer_booking/callbacks.py app/bot/customer_booking/messages.py app/bot/customer_booking/keyboards.py tests/bot/customer_booking/test_callbacks.py tests/bot/customer_booking/test_messages.py tests/bot/customer_booking/test_keyboards.py
git commit -m "feat: add active booking bot helpers"
```

## Task 2: Service Support For Telegram Customer Identity And Active Booking

**Files:**
- Modify: `app/domain/errors.py`
- Modify: `app/db/repositories.py`
- Modify: `app/services/customer_booking.py`
- Test: `tests/services/test_customer_booking.py`

- [ ] **Step 1: Write failing service tests**

Append to `tests/services/test_customer_booking.py`:

```python
from datetime import timedelta

from app.db.models import User
from app.domain.errors import CancellationTooLateError
from app.domain.statuses import BookingStatus
```

Append helper:

```python
async def seed_customer_booking(
    db_session: AsyncSession,
    *,
    telegram_id: int = 1001,
    status: str = "confirmed",
    start_at: datetime = datetime(2026, 5, 18, 10),
) -> tuple[CarWash, Branch, Service, Customer, Booking]:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    user = User(telegram_id=telegram_id, username="ivan")
    db_session.add(user)
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        user_id=user.id,
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
    return car_wash, branch, service, customer, booking
```

Append tests:

```python
async def test_create_booking_links_customer_to_telegram_user(
    db_session: AsyncSession,
) -> None:
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
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[service.id],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        telegram_user_id=1001,
        telegram_username="ivan",
    )

    customer = (await db_session.execute(select(Customer))).scalar_one()
    user = (await db_session.execute(select(User))).scalar_one()
    assert customer.user_id == user.id
    assert user.telegram_id == 1001
    assert user.username == "ivan"


async def test_get_active_booking_returns_future_pending_or_confirmed_booking(
    db_session: AsyncSession,
) -> None:
    car_wash, _, _, _, booking = await seed_customer_booking(
        db_session,
        status="pending",
        start_at=datetime(2026, 5, 18, 10),
    )

    active = await CustomerBookingService(db_session).get_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=1001,
        now=datetime(2026, 5, 18, 8),
    )

    assert active is not None
    assert active.booking_id == booking.id
    assert active.status == "pending"
    assert active.vehicle_plate == "A123BC154"
    assert [service.title for service in active.services] == ["Standard"]


@pytest.mark.parametrize(
    ("status", "start_at"),
    [
        ("cancelled_by_customer", datetime(2026, 5, 18, 10)),
        ("cancelled_by_admin", datetime(2026, 5, 18, 10)),
        ("completed", datetime(2026, 5, 18, 10)),
        ("no_show", datetime(2026, 5, 18, 10)),
        ("confirmed", datetime(2026, 5, 18, 7)),
    ],
)
async def test_get_active_booking_ignores_inactive_or_past_bookings(
    db_session: AsyncSession,
    status: str,
    start_at: datetime,
) -> None:
    car_wash, _, _, _, _ = await seed_customer_booking(
        db_session,
        status=status,
        start_at=start_at,
    )

    active = await CustomerBookingService(db_session).get_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=1001,
        now=datetime(2026, 5, 18, 8),
    )

    assert active is None


async def test_cancel_active_booking_changes_status_when_allowed(
    db_session: AsyncSession,
) -> None:
    car_wash, _, _, _, booking = await seed_customer_booking(
        db_session,
        status="confirmed",
        start_at=datetime(2026, 5, 18, 10),
    )

    cancelled = await CustomerBookingService(db_session).cancel_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=1001,
        now=datetime(2026, 5, 18, 9),
    )

    await db_session.refresh(booking)
    assert cancelled is True
    assert booking.status == BookingStatus.CANCELLED_BY_CUSTOMER.value


async def test_cancel_active_booking_rejects_less_than_one_hour_before_start(
    db_session: AsyncSession,
) -> None:
    car_wash, _, _, _, booking = await seed_customer_booking(
        db_session,
        status="confirmed",
        start_at=datetime(2026, 5, 18, 10),
    )

    with pytest.raises(CancellationTooLateError):
        await CustomerBookingService(db_session).cancel_active_booking(
            car_wash_id=car_wash.id,
            telegram_user_id=1001,
            now=datetime(2026, 5, 18, 9, 1),
        )

    await db_session.refresh(booking)
    assert booking.status == "confirmed"


async def test_cancel_active_booking_returns_false_without_active_booking(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.commit()

    cancelled = await CustomerBookingService(db_session).cancel_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=1001,
        now=datetime(2026, 5, 18, 9),
    )

    assert cancelled is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py -q
```

Expected: FAIL because new service methods and error do not exist, and `create_booking` does not accept Telegram user data.

- [ ] **Step 3: Add cancellation error**

Modify `app/domain/errors.py`:

```python
class CancellationTooLateError(DomainError):
    """Raised when a customer tries to cancel too close to booking start."""
```

- [ ] **Step 4: Add repository helpers**

Modify imports in `app/db/repositories.py`:

```python
from sqlalchemy import Select, update, func, select
from app.db.models import User
```

Add helpers:

```python
ACTIVE_CUSTOMER_BOOKING_STATUSES = [
    BookingStatus.PENDING.value,
    BookingStatus.CONFIRMED.value,
]


async def get_or_create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.flush()
        return user

    if username is not None and user.username != username:
        user.username = username
        await session.flush()
    return user


async def find_active_customer_booking(
    session: AsyncSession,
    *,
    car_wash_id: int,
    telegram_user_id: int,
    now: datetime,
) -> tuple[Booking, Customer] | None:
    result = await session.execute(
        select(Booking, Customer)
        .join(Customer, Booking.customer_id == Customer.id)
        .join(User, Customer.user_id == User.id)
        .where(
            Booking.car_wash_id == car_wash_id,
            User.telegram_id == telegram_user_id,
            Booking.status.in_(ACTIVE_CUSTOMER_BOOKING_STATUSES),
            Booking.start_at > now,
        )
        .order_by(Booking.start_at)
        .limit(1)
    )
    row = result.first()
    if row is None:
        return None
    booking, customer = row
    return booking, customer


async def list_booking_services(
    session: AsyncSession,
    *,
    car_wash_id: int,
    booking_id: int,
) -> list[tuple[BookingServiceModel, Service]]:
    result = await session.execute(
        select(BookingServiceModel, Service)
        .join(Service, BookingServiceModel.service_id == Service.id)
        .where(
            BookingServiceModel.booking_id == booking_id,
            Service.car_wash_id == car_wash_id,
        )
        .order_by(BookingServiceModel.is_main.desc(), Service.id)
    )
    return list(result.all())


async def update_booking_status(
    session: AsyncSession,
    *,
    booking_id: int,
    status: str,
) -> None:
    await session.execute(update(Booking).where(Booking.id == booking_id).values(status=status))
```

Change `create_customer()` signature and body:

```python
async def create_customer(
    session: AsyncSession,
    *,
    car_wash_id: int,
    name: str,
    phone: str,
    vehicle_plate: str,
    user_id: int | None = None,
) -> Customer:
    customer = Customer(
        car_wash_id=car_wash_id,
        user_id=user_id,
        name=name,
        phone=phone,
        vehicle_plate=vehicle_plate,
    )
    session.add(customer)
    await session.flush()
    return customer
```

- [ ] **Step 5: Add active booking DTOs and service methods**

Modify imports in `app/services/customer_booking.py`:

```python
from app.domain.errors import (
    BookingSlotUnavailableError,
    CancellationTooLateError,
    DomainError,
)
from app.domain.statuses import BookingStatus, ensure_transition_allowed
```

Add DTO:

```python
@dataclass(frozen=True, slots=True)
class ActiveCustomerBooking:
    booking_id: int
    status: str
    start_at: datetime
    end_at: datetime
    customer_name: str
    customer_phone: str
    vehicle_plate: str
    services: list[ServiceOption]
```

Change `create_booking()` signature:

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
        telegram_user_id: int | None = None,
        telegram_username: str | None = None,
    ) -> Booking:
```

Before `repositories.create_customer(...)`, add:

```python
        user_id: int | None = None
        if telegram_user_id is not None:
            user = await repositories.get_or_create_user(
                self._session,
                telegram_id=telegram_user_id,
                username=telegram_username,
            )
            user_id = user.id
```

Pass `user_id=user_id` into `create_customer`.

Add methods:

```python
    async def get_active_booking(
        self,
        *,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
    ) -> ActiveCustomerBooking | None:
        current_time = now or datetime.now()
        active = await repositories.find_active_customer_booking(
            self._session,
            car_wash_id=car_wash_id,
            telegram_user_id=telegram_user_id,
            now=current_time,
        )
        if active is None:
            return None

        booking, customer = active
        service_rows = await repositories.list_booking_services(
            self._session,
            car_wash_id=car_wash_id,
            booking_id=booking.id,
        )
        return ActiveCustomerBooking(
            booking_id=booking.id,
            status=booking.status,
            start_at=booking.start_at,
            end_at=booking.end_at,
            customer_name=customer.name,
            customer_phone=customer.phone,
            vehicle_plate=customer.vehicle_plate,
            services=[_to_service_option(service) for _, service in service_rows],
        )

    async def cancel_active_booking(
        self,
        *,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
        cancellation_deadline_minutes: int = 60,
    ) -> bool:
        current_time = now or datetime.now()
        active = await repositories.find_active_customer_booking(
            self._session,
            car_wash_id=car_wash_id,
            telegram_user_id=telegram_user_id,
            now=current_time,
        )
        if active is None:
            return False

        booking, _ = active
        deadline = booking.start_at - timedelta(minutes=cancellation_deadline_minutes)
        if current_time > deadline:
            raise CancellationTooLateError("Booking can no longer be cancelled by customer.")

        ensure_transition_allowed(
            BookingStatus(booking.status),
            BookingStatus.CANCELLED_BY_CUSTOMER,
        )
        await repositories.update_booking_status(
            self._session,
            booking_id=booking.id,
            status=BookingStatus.CANCELLED_BY_CUSTOMER.value,
        )
        await self._session.commit()
        return True
```

- [ ] **Step 6: Run service tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/services/test_customer_booking.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/domain/errors.py app/db/repositories.py app/services/customer_booking.py tests/services/test_customer_booking.py
git commit -m "feat: add active customer booking service"
```

## Task 3: Telegram Handlers For My Booking And Customer Cancellation

**Files:**
- Modify: `app/bot/customer_booking/handlers.py`
- Modify: `tests/bot/customer_booking/fakes.py`
- Modify: `tests/bot/customer_booking/test_handlers.py`

- [ ] **Step 1: Extend fake Telegram objects and service**

Modify `tests/bot/customer_booking/fakes.py` imports:

```python
from datetime import date, datetime, timedelta
from app.domain.errors import CancellationTooLateError
from app.services.customer_booking import ActiveCustomerBooking, ServiceMenu, ServiceOption
```

Add fake user:

```python
@dataclass
class FakeTelegramUser:
    id: int = 1001
    username: str | None = "ivan"
```

Update fake message and callback:

```python
@dataclass
class FakeMessage:
    text: str | None = None
    from_user: FakeTelegramUser | None = field(default_factory=FakeTelegramUser)
    answers: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage = field(default_factory=FakeMessage)
    from_user: FakeTelegramUser | None = field(default_factory=FakeTelegramUser)
    answered: bool = False

    async def answer(self) -> None:
        self.answered = True
```

Extend `FakeCustomerBookingService`:

```python
    active_booking: ActiveCustomerBooking | None = field(
        default_factory=lambda: ActiveCustomerBooking(
            booking_id=15,
            status="confirmed",
            start_at=datetime(2026, 5, 18, 10),
            end_at=datetime(2026, 5, 18, 11),
            customer_name="Иван",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
            services=[option(1, "Стандарт")],
        )
    )
    requested_active_bookings: list[dict[str, Any]] = field(default_factory=list)
    cancel_requests: list[dict[str, Any]] = field(default_factory=list)
    cancel_result: bool = True
    cancel_error: Exception | None = None
```

Add fake methods:

```python
    async def get_active_booking(
        self,
        *,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
    ) -> ActiveCustomerBooking | None:
        self.requested_active_bookings.append(
            {
                "car_wash_id": car_wash_id,
                "telegram_user_id": telegram_user_id,
                "now": now,
            }
        )
        return self.active_booking

    async def cancel_active_booking(
        self,
        *,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
        cancellation_deadline_minutes: int = 60,
    ) -> bool:
        self.cancel_requests.append(
            {
                "car_wash_id": car_wash_id,
                "telegram_user_id": telegram_user_id,
                "now": now,
                "cancellation_deadline_minutes": cancellation_deadline_minutes,
            }
        )
        if self.cancel_error is not None:
            raise self.cancel_error
        return self.cancel_result
```

Update fake `create_booking()` signature and recorded dict:

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
        telegram_user_id: int | None = None,
        telegram_username: str | None = None,
    ) -> Any:
```

Include:

```python
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username,
```

- [ ] **Step 2: Write failing handler tests**

Modify `tests/bot/customer_booking/test_handlers.py` imports:

```python
from app.bot.customer_booking.handlers import (
    handle_active_booking_cancelled,
    handle_active_booking_requested,
    handle_addon_selected,
    handle_addons_done,
    handle_booking_confirmed,
    handle_booking_start,
    handle_cancel_flow,
    handle_change_services,
    handle_change_time,
    handle_date_selected,
    handle_main_service_selected,
    handle_name_received,
    handle_phone_received,
    handle_slot_selected,
    handle_start,
    handle_vehicle_plate_received,
    router,
)
from app.bot.customer_booking.messages import (
    ACTIVE_BOOKING_CANCELLED_TEXT,
    ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT,
    ACTIVE_BOOKING_EMPTY_TEXT,
    NO_SERVICES_TEXT,
    SELECTED_SERVICES_UNAVAILABLE_TEXT,
    SLOT_STALE_TEXT,
)
from app.domain.errors import BookingSlotUnavailableError, CancellationTooLateError, DomainError
```

Update `test_booking_confirmation_creates_booking_and_clears_state` expected dict:

```python
        "telegram_user_id": 1001,
        "telegram_username": "ivan",
```

Append tests:

```python
async def test_active_booking_requested_shows_empty_state_without_booking() -> None:
    service = FakeCustomerBookingService(active_booking=None)
    callback = FakeCallbackQuery(data="book:my_active")

    await handle_active_booking_requested(
        callback,
        customer_booking_service=service,
        default_car_wash_id=10,
    )

    assert service.requested_active_bookings[0]["car_wash_id"] == 10
    assert service.requested_active_bookings[0]["telegram_user_id"] == 1001
    assert first_text(callback.message) == ACTIVE_BOOKING_EMPTY_TEXT


async def test_active_booking_requested_shows_summary_and_cancel_button() -> None:
    service = FakeCustomerBookingService()
    callback = FakeCallbackQuery(data="book:my_active")

    await handle_active_booking_requested(
        callback,
        customer_booking_service=service,
        default_car_wash_id=10,
    )

    assert "Ваша запись" in first_text(callback.message)
    assert "A123BC154" in first_text(callback.message)
    markup = callback.message.answers[0]["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == "book:cancel_active"


async def test_active_booking_cancelled_cancels_booking() -> None:
    service = FakeCustomerBookingService()
    callback = FakeCallbackQuery(data="book:cancel_active")

    await handle_active_booking_cancelled(
        callback,
        customer_booking_service=service,
        default_car_wash_id=10,
    )

    assert service.cancel_requests[0]["car_wash_id"] == 10
    assert service.cancel_requests[0]["telegram_user_id"] == 1001
    assert service.cancel_requests[0]["cancellation_deadline_minutes"] == 60
    assert first_text(callback.message) == ACTIVE_BOOKING_CANCELLED_TEXT


async def test_active_booking_cancelled_handles_late_cancellation() -> None:
    service = FakeCustomerBookingService(
        cancel_error=CancellationTooLateError("Too late.")
    )
    callback = FakeCallbackQuery(data="book:cancel_active")

    await handle_active_booking_cancelled(
        callback,
        customer_booking_service=service,
        default_car_wash_id=10,
    )

    assert first_text(callback.message) == ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT


async def test_active_booking_cancelled_handles_stale_empty_booking() -> None:
    service = FakeCustomerBookingService(cancel_result=False)
    callback = FakeCallbackQuery(data="book:cancel_active")

    await handle_active_booking_cancelled(
        callback,
        customer_booking_service=service,
        default_car_wash_id=10,
    )

    assert first_text(callback.message) == ACTIVE_BOOKING_EMPTY_TEXT
```

Replace `test_booking_callback_handlers_are_state_scoped` with:

```python
def test_booking_callback_handlers_are_state_scoped() -> None:
    callback_handlers = router.callback_query.handlers

    assert callback_handlers[3].filters[0].callback.states == (
        CustomerBookingFlow.choosing_main_service,
    )
    assert callback_handlers[4].filters[0].callback.states == (CustomerBookingFlow.choosing_addons,)
    assert callback_handlers[5].filters[0].callback.states == (CustomerBookingFlow.choosing_addons,)
    assert callback_handlers[6].filters[0].callback.states == (CustomerBookingFlow.choosing_date,)
    assert callback_handlers[7].filters[0].callback.states == (CustomerBookingFlow.choosing_slot,)
    assert callback_handlers[8].filters[0].callback.states == (CustomerBookingFlow.confirming,)
    assert callback_handlers[9].filters[0].callback.states == (CustomerBookingFlow.confirming,)
    assert callback_handlers[10].filters[0].callback.states == (
        CustomerBookingFlow.confirming,
        CustomerBookingFlow.choosing_date,
    )
    assert callback_handlers[11].filters[0].callback.states == (
        CustomerBookingFlow.choosing_main_service,
        CustomerBookingFlow.choosing_addons,
        CustomerBookingFlow.choosing_date,
        CustomerBookingFlow.choosing_slot,
        CustomerBookingFlow.waiting_for_name,
        CustomerBookingFlow.waiting_for_phone,
        CustomerBookingFlow.waiting_for_vehicle_plate,
        CustomerBookingFlow.confirming,
    )
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -q
```

Expected: FAIL because handlers do not exist and booking confirmation does not pass Telegram user data.

- [ ] **Step 4: Add handler imports**

Modify `app/bot/customer_booking/handlers.py` imports:

```python
from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_ACTIVE_BOOKING_CALLBACK,
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CHANGE_TIME_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    MY_ACTIVE_BOOKING_CALLBACK,
    parse_date_callback,
    parse_id_callback,
    parse_slot_callback,
)
from app.bot.customer_booking.keyboards import (
    active_booking_keyboard,
    addons_keyboard,
    booking_entry_keyboard,
    confirmation_keyboard,
    date_keyboard,
    main_services_keyboard,
    no_slots_keyboard,
    slots_keyboard,
)
from app.bot.customer_booking.messages import (
    ACTIVE_BOOKING_CANCELLED_TEXT,
    ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT,
    ACTIVE_BOOKING_EMPTY_TEXT,
    ASK_NAME_TEXT,
    ASK_PHONE_TEXT,
    ASK_VEHICLE_PLATE_TEXT,
    CHOOSE_ADDONS_TEXT,
    CHOOSE_DATE_TEXT,
    CHOOSE_SERVICE_TEXT,
    CHOOSE_SLOT_TEXT,
    CONFIRMED_TEXT,
    INVALID_PHONE_TEXT,
    INVALID_PLATE_TEXT,
    NO_SERVICES_TEXT,
    NO_SLOTS_TEXT,
    PENDING_TEXT,
    SELECTED_SERVICES_UNAVAILABLE_TEXT,
    SLOT_STALE_TEXT,
    START_TEXT,
    format_active_booking_summary,
    format_booking_summary,
)
from app.domain.errors import (
    BookingSlotUnavailableError,
    CancellationTooLateError,
    DomainError,
    ValidationError,
)
```

Add helper:

```python
def _telegram_user(callback_or_message: CallbackQuery | Message) -> tuple[int, str | None]:
    user = callback_or_message.from_user
    if user is None:
        raise RuntimeError("Telegram user is missing.")
    return user.id, user.username
```

- [ ] **Step 5: Pass Telegram user into booking creation**

Modify `handle_booking_confirmed()` before calling service:

```python
    telegram_user_id, telegram_username = _telegram_user(callback)
```

Pass:

```python
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
```

- [ ] **Step 6: Add active booking handlers**

Add before router registrations:

```python
async def handle_active_booking_requested(
    callback: CallbackQuery,
    *,
    customer_booking_service: CustomerBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    telegram_user_id, _ = _telegram_user(callback)
    booking = await customer_booking_service.get_active_booking(
        car_wash_id=default_car_wash_id,
        telegram_user_id=telegram_user_id,
    )
    if booking is None:
        await _callback_message(callback).answer(ACTIVE_BOOKING_EMPTY_TEXT)
        return

    await _callback_message(callback).answer(
        format_active_booking_summary(booking),
        reply_markup=active_booking_keyboard(),
    )


async def handle_active_booking_cancelled(
    callback: CallbackQuery,
    *,
    customer_booking_service: CustomerBookingService,
    default_car_wash_id: int,
) -> None:
    await callback.answer()
    telegram_user_id, _ = _telegram_user(callback)
    try:
        cancelled = await customer_booking_service.cancel_active_booking(
            car_wash_id=default_car_wash_id,
            telegram_user_id=telegram_user_id,
            cancellation_deadline_minutes=60,
        )
    except CancellationTooLateError:
        await _callback_message(callback).answer(ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT)
        return

    text = ACTIVE_BOOKING_CANCELLED_TEXT if cancelled else ACTIVE_BOOKING_EMPTY_TEXT
    await _callback_message(callback).answer(text)
```

- [ ] **Step 7: Register active booking handlers**

Add after `handle_booking_start` registration:

```python
router.callback_query.register(
    handle_active_booking_requested,
    F.data == MY_ACTIVE_BOOKING_CALLBACK,
)
router.callback_query.register(
    handle_active_booking_cancelled,
    F.data == CANCEL_ACTIVE_BOOKING_CALLBACK,
)
```

- [ ] **Step 8: Run handler tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add app/bot/customer_booking/handlers.py tests/bot/customer_booking/fakes.py tests/bot/customer_booking/test_handlers.py
git commit -m "feat: add active booking telegram handlers"
```

## Task 4: Quality Gate

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
git commit -m "chore: pass active booking quality gate"
```

If no files changed, do not create an empty commit.

## Self-Review

Spec coverage:

- View active future booking: Task 2 service DTO/method, Task 3 handler.
- One active future booking: Task 2 query returns one earliest active booking.
- Customer cancellation: Task 2 service method, Task 3 handler.
- Cancellation blocked under 60 minutes: Task 2 `CancellationTooLateError`, Task 3 message.
- Exactly 60 minutes allowed: Task 2 service test.
- Stale callback/no active booking: Task 2 returns false/none, Task 3 empty-state tests.
- Slot freed after cancellation: Task 2 status becomes `cancelled_by_customer`; capacity code already uses only pending/confirmed.
- HTML-safe dynamic summary: Task 1 formatter tests.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified implementation steps remain.

Type consistency:

- `ActiveCustomerBooking` is defined before message tests import it.
- `CancellationTooLateError` is defined before handler/service code imports it.
- Callback constants match keyboard and handler registrations.
- `create_booking` signature changes are propagated to fake service and handler.
