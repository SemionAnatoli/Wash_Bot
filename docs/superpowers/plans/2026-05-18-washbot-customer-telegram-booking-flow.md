# WashBot Customer Telegram Booking Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the customer Telegram booking flow that lets a user select services, choose an available slot, enter contact data, and create a booking through aiogram handlers.

**Architecture:** Keep Telegram code as a thin adapter over `CustomerBookingService`. Put FSM state names, callback parsing, messages, and keyboard builders in small focused modules so handlers stay readable and tests can use fake Telegram/service objects. Database and capacity rules remain in services/repositories/domain.

**Tech Stack:** Python 3.12, aiogram 3.13.1, SQLAlchemy async sessions, pytest, Ruff, mypy.

---

## Scope Notes

This plan implements the customer booking path only. It does not implement admin operations, notification delivery, owner settings editing, payments, Docker, or deployment.

The first release uses configured defaults:

- `default_car_wash_id`
- `default_branch_id`

The flow is Russian-first for user-facing texts.

## File Structure

Create or modify:

- `app/config/settings.py`: add default car wash and branch ids.
- `.env.example`: document default ids.
- `tests/test_settings.py`: cover new settings defaults.
- `app/bot/__init__.py`: bot package marker.
- `app/bot/dependencies.py`: aiogram DB session/service middleware.
- `app/bot/factory.py`: create `Bot` and `Dispatcher`.
- `app/bot/customer_booking/__init__.py`: booking bot package marker.
- `app/bot/customer_booking/states.py`: FSM state group.
- `app/bot/customer_booking/callbacks.py`: callback constants and parser helpers.
- `app/bot/customer_booking/messages.py`: Russian text/formatting helpers.
- `app/bot/customer_booking/keyboards.py`: inline keyboard builders.
- `app/bot/customer_booking/handlers.py`: aiogram router and handlers.
- `tests/bot/customer_booking/fakes.py`: fake message/callback/state/service objects.
- `tests/bot/customer_booking/test_callbacks.py`: callback helper tests.
- `tests/bot/customer_booking/test_messages.py`: message helper tests.
- `tests/bot/customer_booking/test_keyboards.py`: keyboard builder tests.
- `tests/bot/customer_booking/test_handlers.py`: handler tests with fakes.

## Task 1: Default Tenant Settings

**Files:**
- Modify: `app/config/settings.py`
- Modify: `.env.example`
- Modify: `tests/test_settings.py`

- [ ] **Step 1: Write failing settings test**

Append to `tests/test_settings.py`:

```python

def test_settings_load_default_customer_booking_ids() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
    )

    assert settings.default_car_wash_id == 1
    assert settings.default_branch_id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_settings.py::test_settings_load_default_customer_booking_ids -v
```

Expected: FAIL with `AttributeError` because `default_car_wash_id` and `default_branch_id` do not exist.

- [ ] **Step 3: Add settings fields**

Modify `app/config/settings.py`:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "local"
    database_url: AnyUrl
    telegram_bot_token: SecretStr
    default_reminder_before_minutes: int = Field(default=60, ge=0, le=1440)
    default_car_wash_id: int = Field(default=1, ge=1)
    default_branch_id: int = Field(default=1, ge=1)
```

- [ ] **Step 4: Update env example**

Append to `.env.example`:

```env
DEFAULT_CAR_WASH_ID=1
DEFAULT_BRANCH_ID=1
```

- [ ] **Step 5: Run settings tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/test_settings.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/config/settings.py .env.example tests/test_settings.py
git commit -m "feat: add default booking tenant settings"
```

## Task 2: Booking FSM States And Callback Helpers

**Files:**
- Create: `app/bot/__init__.py`
- Create: `app/bot/customer_booking/__init__.py`
- Create: `app/bot/customer_booking/states.py`
- Create: `app/bot/customer_booking/callbacks.py`
- Test: `tests/bot/customer_booking/test_callbacks.py`

- [ ] **Step 1: Write failing callback tests**

Create `tests/bot/customer_booking/test_callbacks.py`:

```python
from datetime import datetime

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    build_addon_callback,
    build_date_callback,
    build_main_service_callback,
    build_slot_callback,
    parse_id_callback,
    parse_slot_callback,
)


def test_booking_callback_builders_are_stable() -> None:
    assert BOOKING_START_CALLBACK == "book:start"
    assert ADDONS_DONE_CALLBACK == "book:addons_done"
    assert CONFIRM_BOOKING_CALLBACK == "book:confirm"
    assert build_main_service_callback(12) == "book:main:12"
    assert build_addon_callback(7) == "book:addon:7"
    assert build_date_callback("2026-05-18") == "book:date:2026-05-18"
    assert build_slot_callback(datetime(2026, 5, 18, 10, 30)) == "book:slot:2026-05-18T10:30"


def test_callback_parsers_return_typed_values() -> None:
    assert parse_id_callback("book:main:12", prefix="book:main") == 12
    assert parse_id_callback("book:addon:7", prefix="book:addon") == 7
    assert parse_slot_callback("book:slot:2026-05-18T10:30") == datetime(2026, 5, 18, 10, 30)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_callbacks.py -v
```

Expected: FAIL because `app.bot.customer_booking.callbacks` does not exist.

- [ ] **Step 3: Add package markers**

Create `app/bot/__init__.py`:

```python
"""Telegram bot adapter package."""
```

Create `app/bot/customer_booking/__init__.py`:

```python
"""Customer booking Telegram flow."""
```

- [ ] **Step 4: Add FSM states**

Create `app/bot/customer_booking/states.py`:

```python
from aiogram.fsm.state import State, StatesGroup


class CustomerBookingFlow(StatesGroup):
    choosing_main_service = State()
    choosing_addons = State()
    choosing_date = State()
    choosing_slot = State()
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_vehicle_plate = State()
    confirming = State()
```

- [ ] **Step 5: Add callback helpers**

Create `app/bot/customer_booking/callbacks.py`:

```python
from datetime import datetime

BOOKING_START_CALLBACK = "book:start"
ADDONS_DONE_CALLBACK = "book:addons_done"
CONFIRM_BOOKING_CALLBACK = "book:confirm"
CHANGE_SERVICES_CALLBACK = "book:change_services"
CHANGE_TIME_CALLBACK = "book:change_time"
CANCEL_FLOW_CALLBACK = "book:cancel_flow"


def build_main_service_callback(service_id: int) -> str:
    return f"book:main:{service_id}"


def build_addon_callback(service_id: int) -> str:
    return f"book:addon:{service_id}"


def build_date_callback(day: str) -> str:
    return f"book:date:{day}"


def build_slot_callback(start_at: datetime) -> str:
    return f"book:slot:{start_at.strftime('%Y-%m-%dT%H:%M')}"


def parse_id_callback(data: str, *, prefix: str) -> int:
    expected_prefix = f"{prefix}:"
    if not data.startswith(expected_prefix):
        raise ValueError("Unexpected callback prefix.")
    return int(data.removeprefix(expected_prefix))


def parse_date_callback(data: str) -> str:
    prefix = "book:date:"
    if not data.startswith(prefix):
        raise ValueError("Unexpected date callback prefix.")
    return data.removeprefix(prefix)


def parse_slot_callback(data: str) -> datetime:
    prefix = "book:slot:"
    if not data.startswith(prefix):
        raise ValueError("Unexpected slot callback prefix.")
    return datetime.fromisoformat(data.removeprefix(prefix))
```

- [ ] **Step 6: Run callback tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_callbacks.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/bot tests/bot/customer_booking/test_callbacks.py
git commit -m "feat: add customer booking callback helpers"
```

## Task 3: Russian Message Helpers

**Files:**
- Create: `app/bot/customer_booking/messages.py`
- Test: `tests/bot/customer_booking/test_messages.py`

- [ ] **Step 1: Write failing message tests**

Create `tests/bot/customer_booking/test_messages.py`:

```python
from datetime import datetime
from decimal import Decimal

from app.bot.customer_booking.messages import (
    format_booking_summary,
    format_duration,
    format_money,
    service_line,
)
from app.services.customer_booking import ServiceOption


def option(
    service_id: int,
    title: str,
    price: str,
    duration_minutes: int,
    *,
    is_addon: bool = False,
) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="addon" if is_addon else "wash",
        price=Decimal(price),
        duration_minutes=duration_minutes,
        is_addon=is_addon,
    )


def test_format_money_and_duration() -> None:
    assert format_money(Decimal("900")) == "900 руб."
    assert format_money(Decimal("900.50")) == "900.50 руб."
    assert format_duration(30) == "30 мин"
    assert format_duration(90) == "1 ч 30 мин"


def test_service_line_contains_title_price_and_duration() -> None:
    text = service_line(option(1, "Стандарт", "900", 60))

    assert text == "Стандарт — 900 руб., 1 ч"


def test_format_booking_summary_contains_customer_choice() -> None:
    text = format_booking_summary(
        main_service=option(1, "Стандарт", "900", 60),
        addons=[option(2, "Воск", "250", 15, is_addon=True)],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Иван",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
    )

    assert "Стандарт" in text
    assert "Воск" in text
    assert "18.05.2026 10:00" in text
    assert "Иван" in text
    assert "+79131234567" in text
    assert "A123BC154" in text
    assert "1 ч 15 мин" in text
    assert "1150 руб." in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_messages.py -v
```

Expected: FAIL because `messages.py` does not exist.

- [ ] **Step 3: Implement message helpers**

Create `app/bot/customer_booking/messages.py`:

```python
from datetime import datetime
from decimal import Decimal

from app.services.customer_booking import ServiceOption

START_TEXT = "Здравствуйте! Я помогу записаться на автомойку."
CHOOSE_SERVICE_TEXT = "Выберите услугу"
CHOOSE_ADDONS_TEXT = "Выберите дополнительные услуги"
CHOOSE_DATE_TEXT = "Выберите дату"
CHOOSE_SLOT_TEXT = "Выберите свободное время"
ASK_NAME_TEXT = "Введите ваше имя"
ASK_PHONE_TEXT = "Введите телефон в формате +7XXXXXXXXXX"
ASK_VEHICLE_PLATE_TEXT = "Введите номер машины, например A123BC154"
NO_SERVICES_TEXT = "Услуги пока не настроены. Свяжитесь с администратором."
NO_SLOTS_TEXT = "На эту дату нет свободного времени. Выберите другую дату или измените услуги."
INVALID_PHONE_TEXT = "Похоже, это не номер телефона. Отправьте номер в формате +7XXXXXXXXXX."
INVALID_PLATE_TEXT = "Введите буквы и цифры номера авто, например A123BC154."
SLOT_STALE_TEXT = "Это время уже не подходит для выбранных услуг. Пожалуйста, выберите другое время."
GENERIC_ERROR_TEXT = "Что-то пошло не так. Попробуйте позже или свяжитесь с администратором."
CONFIRMED_TEXT = "Ваша запись подтверждена."
PENDING_TEXT = "Заявка на запись отправлена. Мы скоро подтвердим её."


def format_money(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    return f"{text} руб."


def format_duration(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} ч")
    if rest:
        parts.append(f"{rest} мин")
    return " ".join(parts) if parts else "0 мин"


def service_line(service: ServiceOption) -> str:
    return (
        f"{service.title} — {format_money(service.price)}, "
        f"{format_duration(service.duration_minutes)}"
    )


def format_booking_summary(
    *,
    main_service: ServiceOption,
    addons: list[ServiceOption],
    start_at: datetime,
    customer_name: str,
    customer_phone: str,
    vehicle_plate: str,
) -> str:
    services = [main_service, *addons]
    total_price = sum((service.price for service in services), Decimal("0"))
    total_duration = sum(service.duration_minutes for service in services)
    addon_lines = "\n".join(f"- {service_line(service)}" for service in addons) or "- Нет"
    return (
        "Проверьте запись:\n\n"
        f"Основная услуга: {service_line(main_service)}\n"
        f"Дополнительно:\n{addon_lines}\n"
        f"Дата и время: {start_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Длительность: {format_duration(total_duration)}\n"
        f"Итого: {format_money(total_price)}\n\n"
        f"Имя: {customer_name}\n"
        f"Телефон: {customer_phone}\n"
        f"Авто: {vehicle_plate}"
    )
```

- [ ] **Step 4: Run message tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_messages.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/bot/customer_booking/messages.py tests/bot/customer_booking/test_messages.py
git commit -m "feat: add customer booking message helpers"
```

## Task 4: Customer Booking Keyboards

**Files:**
- Create: `app/bot/customer_booking/keyboards.py`
- Test: `tests/bot/customer_booking/test_keyboards.py`

- [ ] **Step 1: Write failing keyboard tests**

Create `tests/bot/customer_booking/test_keyboards.py`:

```python
from datetime import date, datetime
from decimal import Decimal

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
)
from app.bot.customer_booking.keyboards import (
    addons_keyboard,
    booking_entry_keyboard,
    confirmation_keyboard,
    date_keyboard,
    main_services_keyboard,
    slots_keyboard,
)
from app.services.customer_booking import ServiceOption


def option(service_id: int, title: str, *, is_addon: bool = False) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="addon" if is_addon else "wash",
        price=Decimal("100"),
        duration_minutes=30,
        is_addon=is_addon,
    )


def callback_grid(markup) -> list[list[str]]:
    return [[button.callback_data for button in row] for row in markup.inline_keyboard]


def text_grid(markup) -> list[list[str]]:
    return [[button.text for button in row] for row in markup.inline_keyboard]


def test_booking_entry_keyboard_contains_start_action() -> None:
    markup = booking_entry_keyboard()

    assert callback_grid(markup) == [[BOOKING_START_CALLBACK]]
    assert text_grid(markup) == [["Записаться"]]


def test_main_services_keyboard_uses_service_callbacks() -> None:
    markup = main_services_keyboard([option(3, "Стандарт")])

    assert callback_grid(markup) == [["book:main:3"]]
    assert text_grid(markup) == [["Стандарт — 100 руб., 30 мин"]]


def test_addons_keyboard_marks_selected_addons_and_has_continue() -> None:
    markup = addons_keyboard(
        [option(5, "Воск", is_addon=True), option(6, "Чернение шин", is_addon=True)],
        selected_ids={5},
    )

    assert callback_grid(markup) == [["book:addon:5"], ["book:addon:6"], [ADDONS_DONE_CALLBACK]]
    assert text_grid(markup)[0] == ["✓ Воск — 100 руб., 30 мин"]
    assert text_grid(markup)[2] == ["Продолжить"]


def test_date_and_slot_keyboards_use_stable_callbacks() -> None:
    dates = [date(2026, 5, 18), date(2026, 5, 19)]
    slots = [datetime(2026, 5, 18, 10), datetime(2026, 5, 18, 10, 30)]

    assert callback_grid(date_keyboard(dates)) == [["book:date:2026-05-18"], ["book:date:2026-05-19"]]
    assert callback_grid(slots_keyboard(slots)) == [["book:slot:2026-05-18T10:00"], ["book:slot:2026-05-18T10:30"]]


def test_confirmation_keyboard_contains_confirm_and_recovery_actions() -> None:
    markup = confirmation_keyboard()

    assert callback_grid(markup) == [
        [CONFIRM_BOOKING_CALLBACK],
        ["book:change_time"],
        ["book:change_services"],
        ["book:cancel_flow"],
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_keyboards.py -v
```

Expected: FAIL because `keyboards.py` does not exist.

- [ ] **Step 3: Implement keyboards**

Create `app/bot/customer_booking/keyboards.py`:

```python
from datetime import date, datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CHANGE_TIME_CALLBACK,
    CONFIRM_BOOKING_CALLBACK,
    build_addon_callback,
    build_date_callback,
    build_main_service_callback,
    build_slot_callback,
)
from app.bot.customer_booking.messages import service_line
from app.services.customer_booking import ServiceOption


def _markup(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def booking_entry_keyboard() -> InlineKeyboardMarkup:
    return _markup([[InlineKeyboardButton(text="Записаться", callback_data=BOOKING_START_CALLBACK)]])


def main_services_keyboard(services: list[ServiceOption]) -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text=service_line(service),
                    callback_data=build_main_service_callback(service.id),
                )
            ]
            for service in services
        ]
    )


def addons_keyboard(
    addons: list[ServiceOption],
    *,
    selected_ids: set[int],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✓ ' if addon.id in selected_ids else ''}{service_line(addon)}",
                callback_data=build_addon_callback(addon.id),
            )
        ]
        for addon in addons
    ]
    rows.append([InlineKeyboardButton(text="Продолжить", callback_data=ADDONS_DONE_CALLBACK)])
    return _markup(rows)


def date_keyboard(dates: list[date]) -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text=day.strftime("%d.%m.%Y"),
                    callback_data=build_date_callback(day.isoformat()),
                )
            ]
            for day in dates
        ]
    )


def slots_keyboard(slots: list[datetime]) -> InlineKeyboardMarkup:
    return _markup(
        [
            [
                InlineKeyboardButton(
                    text=slot.strftime("%H:%M"),
                    callback_data=build_slot_callback(slot),
                )
            ]
            for slot in slots
        ]
    )


def confirmation_keyboard() -> InlineKeyboardMarkup:
    return _markup(
        [
            [InlineKeyboardButton(text="Подтвердить", callback_data=CONFIRM_BOOKING_CALLBACK)],
            [InlineKeyboardButton(text="Выбрать другое время", callback_data=CHANGE_TIME_CALLBACK)],
            [InlineKeyboardButton(text="Изменить услуги", callback_data=CHANGE_SERVICES_CALLBACK)],
            [InlineKeyboardButton(text="Отменить", callback_data=CANCEL_FLOW_CALLBACK)],
        ]
    )
```

- [ ] **Step 4: Run keyboard tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_keyboards.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/bot/customer_booking/keyboards.py tests/bot/customer_booking/test_keyboards.py
git commit -m "feat: add customer booking keyboards"
```

## Task 5: Bot Dependencies And Factory

**Files:**
- Create: `app/bot/dependencies.py`
- Create: `app/bot/factory.py`
- Test: `tests/bot/test_factory.py`

- [ ] **Step 1: Write failing factory tests**

Create `tests/bot/test_factory.py`:

```python
from aiogram import Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.factory import create_dispatcher
from app.config import Settings


def test_create_dispatcher_registers_default_booking_context() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:pass@localhost:5432/washbot",
        telegram_bot_token="token",
        default_car_wash_id=10,
        default_branch_id=20,
    )
    dispatcher = create_dispatcher(
        settings=settings,
        sessionmaker=async_sessionmaker(class_=AsyncSession),
    )

    assert isinstance(dispatcher, Dispatcher)
    assert dispatcher["settings"] is settings
    assert dispatcher["default_car_wash_id"] == 10
    assert dispatcher["default_branch_id"] == 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/test_factory.py -v
```

Expected: FAIL because `app.bot.factory` does not exist.

- [ ] **Step 3: Implement dependency middleware**

Create `app/bot/dependencies.py`:

```python
from collections.abc import Awaitable, Callable
from typing import Any, cast

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.customer_booking import CustomerBookingService


class CustomerBookingServiceMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self._sessionmaker() as session:
            data["db_session"] = session
            data["customer_booking_service"] = CustomerBookingService(session)
            return await handler(event, data)
```

- [ ] **Step 4: Implement dispatcher factory**

Create `app/bot/factory.py`:

```python
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.customer_booking.handlers import router as customer_booking_router
from app.bot.dependencies import CustomerBookingServiceMiddleware
from app.config import Settings


def create_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(
    *,
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher["settings"] = settings
    dispatcher["default_car_wash_id"] = settings.default_car_wash_id
    dispatcher["default_branch_id"] = settings.default_branch_id
    dispatcher.update.middleware(CustomerBookingServiceMiddleware(sessionmaker))
    dispatcher.include_router(customer_booking_router)
    return dispatcher
```

- [ ] **Step 5: Add temporary handlers module so factory imports**

Create `app/bot/customer_booking/handlers.py`:

```python
from aiogram import Router

router = Router(name="customer_booking")
```

- [ ] **Step 6: Run factory tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/test_factory.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/bot/dependencies.py app/bot/factory.py app/bot/customer_booking/handlers.py tests/bot/test_factory.py
git commit -m "feat: add bot dispatcher factory"
```

## Task 6: Start, Service Selection, Add-ons, Dates, And Slots Handlers

**Files:**
- Modify: `app/bot/customer_booking/handlers.py`
- Test: `tests/bot/customer_booking/fakes.py`
- Test: `tests/bot/customer_booking/test_handlers.py`

- [ ] **Step 1: Create test fakes**

Create `tests/bot/customer_booking/fakes.py`:

```python
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.services.customer_booking import ServiceMenu, ServiceOption


@dataclass
class FakeMessage:
    text: str | None = None
    answers: list[dict[str, Any]] = field(default_factory=list)

    async def answer(self, text: str, reply_markup: Any = None) -> None:
        self.answers.append({"text": text, "reply_markup": reply_markup})


@dataclass
class FakeCallbackQuery:
    data: str
    message: FakeMessage = field(default_factory=FakeMessage)
    answered: bool = False

    async def answer(self) -> None:
        self.answered = True


@dataclass
class FakeState:
    data: dict[str, Any] = field(default_factory=dict)
    state: Any = None
    cleared: bool = False

    async def set_state(self, state: Any) -> None:
        self.state = state

    async def update_data(self, **kwargs: Any) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict[str, Any]:
        return dict(self.data)

    async def clear(self) -> None:
        self.data.clear()
        self.state = None
        self.cleared = True


def option(service_id: int, title: str, *, is_addon: bool = False) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="addon" if is_addon else "wash",
        price=Decimal("100"),
        duration_minutes=30,
        is_addon=is_addon,
    )


@dataclass
class FakeCustomerBookingService:
    menu: ServiceMenu = field(
        default_factory=lambda: ServiceMenu(
            main_services=[option(1, "Стандарт")],
            addons=[option(2, "Воск", is_addon=True)],
        )
    )
    slots: list[datetime] = field(default_factory=lambda: [datetime(2026, 5, 18, 10)])
    requested_slots: list[dict[str, Any]] = field(default_factory=list)

    async def get_service_menu(self, *, car_wash_id: int) -> ServiceMenu:
        return self.menu

    async def get_available_slots(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        selected_service_ids: list[int],
        day: date,
    ) -> list[datetime]:
        self.requested_slots.append(
            {
                "car_wash_id": car_wash_id,
                "branch_id": branch_id,
                "selected_service_ids": selected_service_ids,
                "day": day,
            }
        )
        return self.slots
```

- [ ] **Step 2: Write failing handler tests**

Create `tests/bot/customer_booking/test_handlers.py`:

```python
from datetime import date

from app.bot.customer_booking.handlers import (
    handle_addon_selected,
    handle_addons_done,
    handle_booking_start,
    handle_date_selected,
    handle_main_service_selected,
    handle_start,
)
from app.bot.customer_booking.states import CustomerBookingFlow
from tests.bot.customer_booking.fakes import (
    FakeCallbackQuery,
    FakeCustomerBookingService,
    FakeMessage,
    FakeState,
)


def first_text(message: FakeMessage) -> str:
    return message.answers[0]["text"]


async def test_start_shows_booking_entry_keyboard() -> None:
    message = FakeMessage()

    await handle_start(message)

    assert "записаться" in first_text(message).lower()
    assert message.answers[0]["reply_markup"].inline_keyboard[0][0].callback_data == "book:start"


async def test_booking_start_loads_menu_and_sets_context() -> None:
    callback = FakeCallbackQuery(data="book:start")
    state = FakeState()

    await handle_booking_start(
        callback,
        state,
        customer_booking_service=FakeCustomerBookingService(),
        default_car_wash_id=10,
        default_branch_id=20,
    )

    assert state.data["car_wash_id"] == 10
    assert state.data["branch_id"] == 20
    assert state.data["service_menu"].main_services[0].id == 1
    assert state.state == CustomerBookingFlow.choosing_main_service
    assert "Выберите услугу" in first_text(callback.message)


async def test_main_service_selection_stores_service_and_shows_addons() -> None:
    callback = FakeCallbackQuery(data="book:main:1")
    state = FakeState(data={"service_menu": FakeCustomerBookingService().menu})

    await handle_main_service_selected(callback, state)

    assert state.data["main_service_id"] == 1
    assert state.data["addon_service_ids"] == []
    assert state.state == CustomerBookingFlow.choosing_addons
    assert "дополнительные" in first_text(callback.message).lower()


async def test_addon_selection_toggles_selected_id() -> None:
    callback = FakeCallbackQuery(data="book:addon:2")
    state = FakeState(
        data={
            "service_menu": FakeCustomerBookingService().menu,
            "addon_service_ids": [],
        }
    )

    await handle_addon_selected(callback, state)
    await handle_addon_selected(callback, state)

    assert state.data["addon_service_ids"] == []


async def test_addons_done_shows_date_choices() -> None:
    callback = FakeCallbackQuery(data="book:addons_done")
    state = FakeState()

    await handle_addons_done(callback, state)

    assert state.state == CustomerBookingFlow.choosing_date
    assert "Выберите дату" in first_text(callback.message)


async def test_date_selection_requests_slots_for_selected_services() -> None:
    callback = FakeCallbackQuery(data="book:date:2026-05-18")
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "main_service_id": 1,
            "addon_service_ids": [2],
        }
    )
    service = FakeCustomerBookingService()

    await handle_date_selected(callback, state, customer_booking_service=service)

    assert service.requested_slots[0]["selected_service_ids"] == [1, 2]
    assert service.requested_slots[0]["day"] == date(2026, 5, 18)
    assert state.state == CustomerBookingFlow.choosing_slot
    assert "Выберите свободное время" in first_text(callback.message)
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -v
```

Expected: FAIL because handler functions are not implemented.

- [ ] **Step 4: Implement handlers for first half of flow**

Replace `app/bot/customer_booking/handlers.py` with:

```python
from datetime import date, datetime, timedelta
from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.customer_booking.callbacks import (
    ADDONS_DONE_CALLBACK,
    BOOKING_START_CALLBACK,
    build_addon_callback,
    parse_date_callback,
    parse_id_callback,
)
from app.bot.customer_booking.keyboards import (
    addons_keyboard,
    booking_entry_keyboard,
    date_keyboard,
    main_services_keyboard,
    slots_keyboard,
)
from app.bot.customer_booking.messages import (
    CHOOSE_ADDONS_TEXT,
    CHOOSE_DATE_TEXT,
    CHOOSE_SERVICE_TEXT,
    CHOOSE_SLOT_TEXT,
    NO_SERVICES_TEXT,
    NO_SLOTS_TEXT,
    START_TEXT,
)
from app.bot.customer_booking.states import CustomerBookingFlow
from app.services.customer_booking import CustomerBookingService, ServiceMenu

router = Router(name="customer_booking")


def _callback_message(callback: CallbackQuery) -> Message:
    if callback.message is None:
        raise RuntimeError("Callback message is unavailable.")
    return cast(Message, callback.message)


def _next_dates(start: date | None = None) -> list[date]:
    first_day = start or datetime.now().date()
    return [first_day + timedelta(days=offset) for offset in range(7)]


def _selected_service_ids(data: dict[str, Any]) -> list[int]:
    return [data["main_service_id"], *data.get("addon_service_ids", [])]


async def handle_start(message: Message) -> None:
    await message.answer(START_TEXT, reply_markup=booking_entry_keyboard())


async def handle_booking_start(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
    default_car_wash_id: int,
    default_branch_id: int,
) -> None:
    await callback.answer()
    menu = await customer_booking_service.get_service_menu(car_wash_id=default_car_wash_id)
    await state.update_data(
        car_wash_id=default_car_wash_id,
        branch_id=default_branch_id,
        service_menu=menu,
    )
    if not menu.main_services:
        await _callback_message(callback).answer(NO_SERVICES_TEXT)
        return
    await state.set_state(CustomerBookingFlow.choosing_main_service)
    await _callback_message(callback).answer(
        CHOOSE_SERVICE_TEXT,
        reply_markup=main_services_keyboard(menu.main_services),
    )


async def handle_main_service_selected(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    menu: ServiceMenu = data["service_menu"]
    service_id = parse_id_callback(callback.data or "", prefix="book:main")
    await state.update_data(main_service_id=service_id, addon_service_ids=[])
    await state.set_state(CustomerBookingFlow.choosing_addons)
    await _callback_message(callback).answer(
        CHOOSE_ADDONS_TEXT,
        reply_markup=addons_keyboard(menu.addons, selected_ids=set()),
    )


async def handle_addon_selected(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    menu: ServiceMenu = data["service_menu"]
    selected = set(data.get("addon_service_ids", []))
    addon_id = parse_id_callback(callback.data or "", prefix="book:addon")
    if addon_id in selected:
        selected.remove(addon_id)
    else:
        selected.add(addon_id)
    selected_ids = sorted(selected)
    await state.update_data(addon_service_ids=selected_ids)
    await _callback_message(callback).answer(
        CHOOSE_ADDONS_TEXT,
        reply_markup=addons_keyboard(menu.addons, selected_ids=set(selected_ids)),
    )


async def handle_addons_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(CustomerBookingFlow.choosing_date)
    await _callback_message(callback).answer(CHOOSE_DATE_TEXT, reply_markup=date_keyboard(_next_dates()))


async def handle_date_selected(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    await callback.answer()
    data = await state.get_data()
    selected_day = date.fromisoformat(parse_date_callback(callback.data or ""))
    slots = await customer_booking_service.get_available_slots(
        car_wash_id=data["car_wash_id"],
        branch_id=data["branch_id"],
        selected_service_ids=_selected_service_ids(data),
        day=selected_day,
    )
    await state.update_data(selected_date=selected_day.isoformat())
    if not slots:
        await _callback_message(callback).answer(
            NO_SLOTS_TEXT,
            reply_markup=date_keyboard(_next_dates(selected_day)),
        )
        return
    await state.set_state(CustomerBookingFlow.choosing_slot)
    await _callback_message(callback).answer(CHOOSE_SLOT_TEXT, reply_markup=slots_keyboard(slots))


router.message.register(handle_start, CommandStart())
router.callback_query.register(handle_booking_start, F.data == BOOKING_START_CALLBACK)
router.callback_query.register(handle_main_service_selected, F.data.startswith("book:main:"))
router.callback_query.register(handle_addon_selected, F.data.startswith("book:addon:"))
router.callback_query.register(handle_addons_done, F.data == ADDONS_DONE_CALLBACK)
router.callback_query.register(handle_date_selected, F.data.startswith("book:date:"))
```

- [ ] **Step 5: Run handler tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/bot/customer_booking/handlers.py tests/bot/customer_booking/fakes.py tests/bot/customer_booking/test_handlers.py
git commit -m "feat: add customer booking selection handlers"
```

## Task 7: Customer Input And Booking Confirmation Handlers

**Files:**
- Modify: `app/bot/customer_booking/handlers.py`
- Modify: `tests/bot/customer_booking/fakes.py`
- Modify: `tests/bot/customer_booking/test_handlers.py`

- [ ] **Step 1: Extend fake service with booking creation**

Modify `FakeCustomerBookingService` in `tests/bot/customer_booking/fakes.py`:

```python
    created_bookings: list[dict[str, Any]] = field(default_factory=list)
    booking_status: str = "confirmed"

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
    ) -> Any:
        self.created_bookings.append(
            {
                "car_wash_id": car_wash_id,
                "branch_id": branch_id,
                "selected_service_ids": selected_service_ids,
                "start_at": start_at,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "vehicle_plate": vehicle_plate,
            }
        )
        return type("BookingResult", (), {"status": self.booking_status})()
```

- [ ] **Step 2: Write failing confirmation tests**

Append to `tests/bot/customer_booking/test_handlers.py`:

```python
from datetime import datetime

from app.bot.customer_booking.handlers import (
    handle_booking_confirmed,
    handle_name_received,
    handle_phone_received,
    handle_slot_selected,
    handle_vehicle_plate_received,
)


async def test_slot_selection_stores_start_and_asks_for_name() -> None:
    callback = FakeCallbackQuery(data="book:slot:2026-05-18T10:00")
    state = FakeState()

    await handle_slot_selected(callback, state)

    assert state.data["start_at"] == "2026-05-18T10:00:00"
    assert state.state == CustomerBookingFlow.waiting_for_name
    assert "имя" in first_text(callback.message).lower()


async def test_invalid_phone_keeps_phone_state() -> None:
    message = FakeMessage(text="123")
    state = FakeState()

    await handle_phone_received(message, state)

    assert state.state == CustomerBookingFlow.waiting_for_phone
    assert "номер телефона" in first_text(message).lower()


async def test_customer_input_reaches_confirmation_summary() -> None:
    menu = FakeCustomerBookingService().menu
    state = FakeState(
        data={
            "service_menu": menu,
            "main_service_id": 1,
            "addon_service_ids": [2],
            "start_at": "2026-05-18T10:00:00",
        }
    )

    await handle_name_received(FakeMessage(text=" Иван "), state)
    await handle_phone_received(FakeMessage(text="8 (913) 123-45-67"), state)
    plate_message = FakeMessage(text="a123bc154")
    await handle_vehicle_plate_received(plate_message, state)

    assert state.data["customer_name"] == "Иван"
    assert state.data["customer_phone"] == "+79131234567"
    assert state.data["vehicle_plate"] == "A123BC154"
    assert state.state == CustomerBookingFlow.confirming
    assert "Проверьте запись" in first_text(plate_message)


async def test_booking_confirmation_creates_booking_and_clears_state() -> None:
    service = FakeCustomerBookingService()
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "service_menu": service.menu,
            "main_service_id": 1,
            "addon_service_ids": [2],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "Иван",
            "customer_phone": "+79131234567",
            "vehicle_plate": "A123BC154",
        }
    )
    callback = FakeCallbackQuery(data="book:confirm")

    await handle_booking_confirmed(callback, state, customer_booking_service=service)

    assert service.created_bookings[0]["selected_service_ids"] == [1, 2]
    assert service.created_bookings[0]["start_at"] == datetime(2026, 5, 18, 10)
    assert "подтверждена" in first_text(callback.message).lower()
    assert state.cleared is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -v
```

Expected: FAIL because input/confirmation handlers are not implemented.

- [ ] **Step 4: Implement input and confirmation handlers**

Add imports in `app/bot/customer_booking/handlers.py`:

```python
from app.bot.customer_booking.callbacks import CONFIRM_BOOKING_CALLBACK, parse_slot_callback
from app.bot.customer_booking.keyboards import confirmation_keyboard
from app.bot.customer_booking.messages import (
    ASK_NAME_TEXT,
    ASK_PHONE_TEXT,
    ASK_VEHICLE_PLATE_TEXT,
    CONFIRMED_TEXT,
    INVALID_PHONE_TEXT,
    INVALID_PLATE_TEXT,
    PENDING_TEXT,
    format_booking_summary,
)
from app.domain.errors import ValidationError
from app.domain.validation import normalize_name, normalize_phone, normalize_vehicle_plate
```

Add helpers and handlers before router registrations:

```python
def _find_service(menu: ServiceMenu, service_id: int):
    for service in [*menu.main_services, *menu.addons]:
        if service.id == service_id:
            return service
    raise ValueError("Selected service is missing from stored menu.")


def _selected_options(data: dict[str, Any]) -> tuple[Any, list[Any]]:
    menu: ServiceMenu = data["service_menu"]
    main_service = _find_service(menu, data["main_service_id"])
    addons = [_find_service(menu, service_id) for service_id in data.get("addon_service_ids", [])]
    return main_service, addons


async def handle_slot_selected(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    start_at = parse_slot_callback(callback.data or "")
    await state.update_data(start_at=start_at.isoformat())
    await state.set_state(CustomerBookingFlow.waiting_for_name)
    await _callback_message(callback).answer(ASK_NAME_TEXT)


async def handle_name_received(message: Message, state: FSMContext) -> None:
    try:
        name = normalize_name(message.text or "")
    except ValidationError:
        await state.set_state(CustomerBookingFlow.waiting_for_name)
        await message.answer(ASK_NAME_TEXT)
        return
    await state.update_data(customer_name=name)
    await state.set_state(CustomerBookingFlow.waiting_for_phone)
    await message.answer(ASK_PHONE_TEXT)


async def handle_phone_received(message: Message, state: FSMContext) -> None:
    try:
        phone = normalize_phone(message.text or "")
    except ValidationError:
        await state.set_state(CustomerBookingFlow.waiting_for_phone)
        await message.answer(INVALID_PHONE_TEXT)
        return
    await state.update_data(customer_phone=phone)
    await state.set_state(CustomerBookingFlow.waiting_for_vehicle_plate)
    await message.answer(ASK_VEHICLE_PLATE_TEXT)


async def handle_vehicle_plate_received(message: Message, state: FSMContext) -> None:
    try:
        vehicle_plate = normalize_vehicle_plate(message.text or "")
    except ValidationError:
        await state.set_state(CustomerBookingFlow.waiting_for_vehicle_plate)
        await message.answer(INVALID_PLATE_TEXT)
        return
    await state.update_data(vehicle_plate=vehicle_plate)
    data = await state.get_data()
    main_service, addons = _selected_options(data)
    await state.set_state(CustomerBookingFlow.confirming)
    await message.answer(
        format_booking_summary(
            main_service=main_service,
            addons=addons,
            start_at=datetime.fromisoformat(data["start_at"]),
            customer_name=data["customer_name"],
            customer_phone=data["customer_phone"],
            vehicle_plate=vehicle_plate,
        ),
        reply_markup=confirmation_keyboard(),
    )


async def handle_booking_confirmed(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    customer_booking_service: CustomerBookingService,
) -> None:
    await callback.answer()
    data = await state.get_data()
    booking = await customer_booking_service.create_booking(
        car_wash_id=data["car_wash_id"],
        branch_id=data["branch_id"],
        selected_service_ids=_selected_service_ids(data),
        start_at=datetime.fromisoformat(data["start_at"]),
        customer_name=data["customer_name"],
        customer_phone=data["customer_phone"],
        vehicle_plate=data["vehicle_plate"],
    )
    await state.clear()
    text = CONFIRMED_TEXT if booking.status == "confirmed" else PENDING_TEXT
    await _callback_message(callback).answer(text)
```

Add router registrations:

```python
router.callback_query.register(handle_slot_selected, F.data.startswith("book:slot:"))
router.message.register(handle_name_received, CustomerBookingFlow.waiting_for_name)
router.message.register(handle_phone_received, CustomerBookingFlow.waiting_for_phone)
router.message.register(handle_vehicle_plate_received, CustomerBookingFlow.waiting_for_vehicle_plate)
router.callback_query.register(handle_booking_confirmed, F.data == CONFIRM_BOOKING_CALLBACK)
```

- [ ] **Step 5: Run handler tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/bot/customer_booking/handlers.py tests/bot/customer_booking/fakes.py tests/bot/customer_booking/test_handlers.py
git commit -m "feat: add customer booking confirmation handlers"
```

## Task 8: Recovery And Cancel Handlers

**Files:**
- Modify: `app/bot/customer_booking/handlers.py`
- Modify: `tests/bot/customer_booking/test_handlers.py`

- [ ] **Step 1: Write failing recovery tests**

Append to `tests/bot/customer_booking/test_handlers.py`:

```python
from app.bot.customer_booking.handlers import (
    handle_cancel_flow,
    handle_change_services,
    handle_change_time,
)


async def test_change_time_returns_to_date_selection() -> None:
    callback = FakeCallbackQuery(data="book:change_time")
    state = FakeState()

    await handle_change_time(callback, state)

    assert state.state == CustomerBookingFlow.choosing_date
    assert "Выберите дату" in first_text(callback.message)


async def test_change_services_returns_to_menu() -> None:
    callback = FakeCallbackQuery(data="book:change_services")
    state = FakeState(data={"service_menu": FakeCustomerBookingService().menu})

    await handle_change_services(callback, state)

    assert state.state == CustomerBookingFlow.choosing_main_service
    assert "Выберите услугу" in first_text(callback.message)


async def test_cancel_flow_clears_state() -> None:
    callback = FakeCallbackQuery(data="book:cancel_flow")
    state = FakeState(data={"main_service_id": 1})

    await handle_cancel_flow(callback, state)

    assert state.cleared is True
    assert "отменена" in first_text(callback.message).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -v
```

Expected: FAIL because recovery handlers are not implemented.

- [ ] **Step 3: Implement recovery handlers**

Add imports in `app/bot/customer_booking/handlers.py`:

```python
from app.bot.customer_booking.callbacks import (
    CANCEL_FLOW_CALLBACK,
    CHANGE_SERVICES_CALLBACK,
    CHANGE_TIME_CALLBACK,
)
```

Add handlers:

```python
async def handle_change_time(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(CustomerBookingFlow.choosing_date)
    await _callback_message(callback).answer(CHOOSE_DATE_TEXT, reply_markup=date_keyboard(_next_dates()))


async def handle_change_services(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    menu: ServiceMenu = data["service_menu"]
    await state.update_data(main_service_id=None, addon_service_ids=[])
    await state.set_state(CustomerBookingFlow.choosing_main_service)
    await _callback_message(callback).answer(
        CHOOSE_SERVICE_TEXT,
        reply_markup=main_services_keyboard(menu.main_services),
    )


async def handle_cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _callback_message(callback).answer("Запись отменена.")
```

Add router registrations:

```python
router.callback_query.register(handle_change_time, F.data == CHANGE_TIME_CALLBACK)
router.callback_query.register(handle_change_services, F.data == CHANGE_SERVICES_CALLBACK)
router.callback_query.register(handle_cancel_flow, F.data == CANCEL_FLOW_CALLBACK)
```

- [ ] **Step 4: Run handler tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/bot/customer_booking/handlers.py tests/bot/customer_booking/test_handlers.py
git commit -m "feat: add customer booking recovery handlers"
```

## Task 9: Domain Error Handling For Stale Slots

**Files:**
- Modify: `app/bot/customer_booking/handlers.py`
- Modify: `tests/bot/customer_booking/fakes.py`
- Modify: `tests/bot/customer_booking/test_handlers.py`

- [ ] **Step 1: Extend fake service with create failure**

Modify `FakeCustomerBookingService` in `tests/bot/customer_booking/fakes.py`:

```python
    create_error: Exception | None = None
```

At the start of `create_booking`, before appending to `created_bookings`, add:

```python
        if self.create_error is not None:
            raise self.create_error
```

- [ ] **Step 2: Write failing stale-slot test**

Append to `tests/bot/customer_booking/test_handlers.py`:

```python
from app.domain.errors import DomainError


async def test_booking_confirmation_handles_stale_slot() -> None:
    service = FakeCustomerBookingService(create_error=DomainError("Capacity is full."))
    state = FakeState(
        data={
            "car_wash_id": 10,
            "branch_id": 20,
            "service_menu": service.menu,
            "main_service_id": 1,
            "addon_service_ids": [],
            "start_at": "2026-05-18T10:00:00",
            "customer_name": "Иван",
            "customer_phone": "+79131234567",
            "vehicle_plate": "A123BC154",
        }
    )
    callback = FakeCallbackQuery(data="book:confirm")

    await handle_booking_confirmed(callback, state, customer_booking_service=service)

    assert "уже не подходит" in first_text(callback.message)
    assert callback.message.answers[0]["reply_markup"].inline_keyboard[0][0].callback_data == "book:confirm"
    assert state.state == CustomerBookingFlow.confirming
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py::test_booking_confirmation_handles_stale_slot -v
```

Expected: FAIL because `DomainError` is not caught.

- [ ] **Step 4: Catch expected domain errors**

Add imports in `app/bot/customer_booking/handlers.py`:

```python
from app.domain.errors import DomainError
from app.bot.customer_booking.messages import SLOT_STALE_TEXT
```

Wrap `create_booking` in `handle_booking_confirmed`:

```python
    try:
        booking = await customer_booking_service.create_booking(
            car_wash_id=data["car_wash_id"],
            branch_id=data["branch_id"],
            selected_service_ids=_selected_service_ids(data),
            start_at=datetime.fromisoformat(data["start_at"]),
            customer_name=data["customer_name"],
            customer_phone=data["customer_phone"],
            vehicle_plate=data["vehicle_plate"],
        )
    except DomainError:
        await state.set_state(CustomerBookingFlow.confirming)
        await _callback_message(callback).answer(
            SLOT_STALE_TEXT,
            reply_markup=confirmation_keyboard(),
        )
        return
```

- [ ] **Step 5: Run handler tests**

Run:

```bash
C:\Users\Семен\AppData\Local\Programs\Python\Python312\python.exe -m pytest tests/bot/customer_booking/test_handlers.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/bot/customer_booking/handlers.py tests/bot/customer_booking/fakes.py tests/bot/customer_booking/test_handlers.py
git commit -m "feat: handle stale customer booking slots"
```

## Task 10: Quality Gate

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
git commit -m "chore: pass customer telegram booking quality gate"
```

If no files changed, do not create an empty commit.

## Self-Review

Spec coverage:

- `/start` and booking entry point: Task 6.
- Service selection and add-ons: Tasks 4 and 6.
- Date and slot selection through `CustomerBookingService`: Task 6.
- Name, phone, and vehicle plate input: Task 7.
- Confirmation and booking creation: Task 7.
- Auto/manual status message: Task 7.
- Recovery for stale slots and capacity errors: Tasks 8 and 9.
- Thin Telegram layer over service: Tasks 5-9.
- Russian-first messages: Task 3.
- Default one-car-wash/one-branch configuration: Task 1.
- Test coverage and quality gate: Tasks 1-10.

Intentional gaps:

- Admin operations are not included.
- Real Telegram notification delivery is not included.
- Owner settings editing is not included.
- Docker/deployment changes are not included.

Placeholder scan:

- The plan contains no `TBD`, `TODO`, or unspecified implementation steps.
- Each new module has concrete test and implementation guidance.

Type consistency:

- Callback constants used by keyboards and handlers are defined in Task 2.
- `CustomerBookingFlow` states used in handlers are defined in Task 2.
- Message constants and helpers used by handlers are defined in Task 3.
- Keyboard functions used by handlers are defined in Task 4.
- Fake service signatures match `CustomerBookingService` methods used by handlers.
