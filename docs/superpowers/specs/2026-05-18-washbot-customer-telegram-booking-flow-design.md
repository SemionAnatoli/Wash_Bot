# WashBot Customer Telegram Booking Flow Design

## 1. Purpose

This slice turns the existing customer booking application service into a usable
Telegram customer flow. A customer should be able to open the bot, choose a main
service, choose optional add-ons, pick a date and available time, enter name,
phone, and vehicle plate, then create a booking.

The goal is a demonstrable customer booking MVP path. This slice does not build
admin operations, notification delivery, owner settings, payments, deployment, or
return-visit campaigns.

## 2. Architecture

The Telegram layer stays thin and delegates business decisions to services.

New modules:

- `app/bot/factory.py`: creates `Bot`, `Dispatcher`, routers, and dependencies.
- `app/bot/customer_booking/states.py`: FSM states for the booking flow.
- `app/bot/customer_booking/callbacks.py`: typed callback data factories.
- `app/bot/customer_booking/keyboards.py`: inline/reply keyboard builders.
- `app/bot/customer_booking/messages.py`: user-facing text helpers.
- `app/bot/customer_booking/handlers.py`: aiogram handlers for customer booking.
- `app/bot/dependencies.py`: session/service dependency wiring.
- `tests/bot/customer_booking`: handler and keyboard tests with fake service/session
  objects.

Dependency direction:

`bot handlers -> CustomerBookingService -> repositories/domain`

Handlers must not query SQLAlchemy models directly and must not recalculate
capacity rules.

## 3. Flow

The first release assumes one configured car wash and one default branch. The bot
uses settings such as `default_car_wash_id` and `default_branch_id` for this
slice. Multi-branch selection remains compatible with the callback structure but
is not required now.

Customer flow:

1. `/start` shows greeting and `Book a wash`.
2. `Book a wash` loads active service menu.
3. Customer selects exactly one main service.
4. Bot shows optional add-ons and allows toggling several add-ons.
5. Customer presses `Continue`.
6. Bot shows date choices: today, tomorrow, and the next 5 days.
7. Customer selects a date.
8. Bot calls `get_available_slots` using selected services.
9. Bot shows available slots as inline buttons.
10. Customer selects a slot.
11. Bot asks for name.
12. Bot asks for phone.
13. Bot asks for vehicle plate.
14. Bot shows confirmation summary.
15. Customer confirms.
16. Bot calls `create_booking`.
17. Bot shows confirmed or pending message based on booking status.

The FSM stores only small primitives:

- `car_wash_id`
- `branch_id`
- `main_service_id`
- `addon_service_ids`
- `selected_date`
- `start_at`
- `customer_name`
- `customer_phone`
- `vehicle_plate`

## 4. User Messages

Messages should be short, operational, and Russian-first for the initial launch.

Examples:

- Main action: `Выберите услугу`
- No services: `Услуги пока не настроены. Свяжитесь с администратором.`
- No slots: `На эту дату нет свободного времени. Выберите другую дату или измените услуги.`
- Slot stale: `Это время уже не подходит для выбранных услуг. Пожалуйста, выберите другое время.`
- Invalid phone: `Похоже, это не номер телефона. Отправьте номер в формате +7XXXXXXXXXX.`
- Invalid plate: `Введите буквы и цифры номера авто, например A123BC154.`
- Success auto-confirmed: `Ваша запись подтверждена.`
- Success manual: `Заявка на запись отправлена. Мы скоро подтвердим её.`

Errors must not expose tracebacks, database IDs, tokens, or internal exception
details.

## 5. Callback Design

Callbacks should be compact and stable:

- `book:start`
- `book:main:<service_id>`
- `book:addon:<service_id>`
- `book:addons_done`
- `book:date:<YYYY-MM-DD>`
- `book:slot:<YYYY-MM-DDTHH:MM>`
- `book:confirm`
- `book:change_services`
- `book:change_time`
- `book:cancel_flow`

If callback length becomes a problem, replace raw strings with aiogram
`CallbackData` factories using short prefixes.

## 6. Validation And Error Handling

Input validation uses existing domain validators:

- `normalize_name`
- `normalize_phone`
- `normalize_vehicle_plate`

Invalid input keeps the customer in the same FSM state and asks only for the
current field again.

Expected service errors:

- missing branch or services;
- no available slots;
- slot became unavailable before confirmation;
- validation error;
- capacity full.

For expected errors, the bot shows recovery buttons:

- `Выбрать другое время`
- `Изменить услуги`
- `Отменить запись`

Unexpected errors are logged and produce a generic customer message:

`Что-то пошло не так. Попробуйте позже или свяжитесь с администратором.`

## 7. Testing Strategy

This slice should be implemented with TDD.

Unit tests:

- keyboard builders render the expected buttons;
- message helpers format price, duration, date, and confirmation summary;
- callback parsing routes to the expected state changes.

Handler tests:

- `/start` shows booking entry point;
- service selection stores one main service;
- add-on toggling adds and removes ids;
- date selection requests slots from `CustomerBookingService`;
- no-slot response offers another date or service change;
- invalid phone keeps the phone state;
- invalid plate keeps the plate state;
- confirmation calls `create_booking` with normalized user data;
- stale slot/domain error returns recovery actions.

Integration boundary:

- use fake `CustomerBookingService` for handler tests;
- keep existing service integration tests as the source of truth for database and
  scheduling behavior.

Quality gate:

- `pytest -q`
- `ruff check .`
- `ruff format --check .`
- `mypy app`

## 8. Acceptance Criteria

This slice is complete when:

- a customer can complete the booking flow through Telegram handlers;
- the flow uses the existing `CustomerBookingService`;
- selected services and add-ons affect available slots;
- invalid name, phone, and plate inputs do not reset the flow;
- stale or unavailable slots produce a clear recovery path;
- booking confirmation shows the correct auto/manual status;
- tests cover the happy path and key failure paths;
- the full quality gate passes.

## 9. Out Of Scope

- Admin Telegram operations.
- Owner settings editor.
- Notification worker delivery.
- Return-visit reminders.
- Payments.
- Web admin panel.
- Deployment and Docker changes.
