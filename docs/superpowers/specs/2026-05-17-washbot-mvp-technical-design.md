# WashBot MVP Technical Design

## 1. Purpose

WashBot MVP is a Telegram-first booking product for one initial car wash, designed to be sellable as a working release before broader scaling. The first release should support daily booking operations for one car wash while keeping the code and database ready for future multi-tenant use.

The MVP must prove that customers can book without calling, administrators can manage bookings in Telegram, reminders are sent automatically, and the system prevents double-booking or time overlap.

## 2. Chosen Approach

WashBot will be built as a modular monolith in one Python repository.

Runtime processes:

- `bot`: Telegram bot built with aiogram.
- `api`: FastAPI application for internal/service endpoints and future web admin support.
- `worker`: background processing for reminders and return-visit notifications.
- `postgres`: primary PostgreSQL database.

The target deployment model is one VPS with Docker Compose. For the first release, the product runs for one car wash, but business data includes `car_wash_id` so the system can later support multiple car washes without rewriting the core model.

## 3. Technology Stack

- Python.
- aiogram for Telegram bot interactions.
- FastAPI for internal API and future admin panel integration.
- PostgreSQL for persistent storage.
- SQLAlchemy 2.x ORM with typed declarative models.
- Alembic for database migrations.
- pytest for automated tests.
- Ruff for formatting and linting.
- mypy or pyright for static type checks.
- Docker Compose for local and VPS deployment.

## 4. Architecture

The codebase should separate interfaces from business logic.

Main modules:

- `app/domain`: business rules, entities, value objects, status rules, validation, time interval logic.
- `app/services`: application use cases such as booking creation, cancellation, slot search, status changes, blocking time, and notification planning.
- `app/db`: SQLAlchemy models, repositories, database session management, migrations.
- `app/bot`: aiogram handlers, keyboards, FSM states, Telegram-specific input/output.
- `app/api`: FastAPI routers, request/response schemas, health checks, internal operations.
- `app/worker`: notification processing and scheduled background jobs.
- `app/config`: environment-based settings, tokens, database URL, runtime flags.

Dependency direction:

`bot/api/worker -> services -> domain/db`

The `domain` module must not depend on Telegram, FastAPI, SQLAlchemy sessions, or worker-specific code.

## 5. MVP Feature Scope

Customer features:

- Open Telegram bot.
- Start booking.
- Select branch, with one default branch in the first release.
- Select one main service.
- Select optional add-ons.
- See total price and total duration.
- Select date.
- Select available time slot.
- Enter name, phone, and vehicle plate number.
- Confirm booking.
- Receive booking confirmation or pending confirmation message.
- View active booking.
- Cancel booking when cancellation rules allow it.

Administrator features in Telegram:

- View today's bookings.
- View bookings by selected date.
- Confirm booking when confirmation mode is manual.
- Cancel booking.
- Mark booking as completed.
- Mark booking as no-show.
- Add manual booking.
- Block time slot.
- Receive notification about new booking.
- Edit basic services, prices, and durations.

Owner settings in Telegram:

- Car wash name.
- Branch address.
- Working hours.
- Number of identical wash bays.
- Confirmation mode: `auto` or `manual`.
- Reminder timing.
- Return-visit reminder delay.
- Administrator Telegram IDs.

## 6. Service Catalog

The MVP includes a small editable starter catalog. Long-running services such as full dry cleaning, detailing, polishing, ceramic coating, and complex protection packages are excluded from MVP.

Categories:

- `wash`
- `interior`
- `addon`

Starter services:

| Service | Category | Duration | Add-on |
| --- | --- | ---: | --- |
| Express wash | wash | 20 min | No |
| Body wash | wash | 30 min | No |
| Standard package | wash | 60 min | No |
| Full package | wash | 90 min | No |
| Interior cleaning | interior | 45 min | No |
| Engine wash | wash | 45 min | No |
| Tire blackening | addon | 10 min | Yes |
| Liquid wax | addon | 15 min | Yes |
| Insect/bitumen removal | addon | 20 min | Yes |
| Interior ozonation | addon | 30 min | Yes |

Selection rule:

- A customer selects exactly one main service.
- A customer may select multiple add-ons.
- Booking duration is the main service duration plus selected add-on durations plus any configured buffer.

This avoids strange combinations such as choosing multiple main wash packages in one booking.

## 7. Data Model

Core tables:

- `car_washes`: tenant/business.
- `branches`: branch address and `bay_count`.
- `users`: Telegram users and system users.
- `customers`: customer profile with name, phone, and vehicle plate.
- `admins`: admin access linked to car wash and optionally branch.
- `service_categories`: service grouping.
- `services`: title, description, price, `duration_minutes`, category, `is_addon`, `is_active`.
- `working_hours`: branch working hours by weekday.
- `blocked_slots`: manually unavailable intervals.
- `bookings`: booking start/end time, status, customer, branch, car wash.
- `booking_services`: selected main service and add-ons.
- `notification_jobs`: scheduled notification tasks.
- `settings`: confirmation mode, reminder timing, return-visit delay, cancellation rules.

Every business entity must include `car_wash_id` where tenant ownership is relevant.

## 8. Booking And Slot Rules

The first scheduling model uses one branch with `N` identical wash bays. Bays are treated as shared capacity, not as individually assigned resources.

Slot generation:

- The customer chooses services before choosing time.
- The system calculates `total_duration_minutes`.
- Slots are generated by branch working hours.
- Default slot step is 30 minutes.
- A slot is available only if the full interval `[start_at, end_at)` fits into working hours.
- A slot is available only if it does not overlap blocked slots.
- A slot is available only if active overlapping bookings stay below `bay_count` throughout the whole interval.

Capacity statuses:

- `pending` occupies capacity.
- `confirmed` occupies capacity.
- `cancelled_by_customer`, `cancelled_by_admin`, `completed`, and `no_show` do not occupy future capacity.

The system must not check only the slot start time. It must check the full booking interval. For example, if the free window is `12:00-13:00` and selected services take 90 minutes, the `12:00` slot must not be shown.

Before saving a booking, availability must be checked again inside a database transaction. This protects against two customers trying to take the last available capacity at the same time.

If a previously shown slot becomes unavailable, the customer sees:

> This time no longer fits the selected services. The total booking duration is 1 h 30 min, but the free window is shorter. Please choose another time.

Buttons:

- Choose another time.
- Change services.
- Contact administrator.

## 9. Booking Statuses

Statuses:

- `pending`
- `confirmed`
- `cancelled_by_customer`
- `cancelled_by_admin`
- `completed`
- `no_show`

Confirmation mode is configured per car wash:

- `auto`: booking becomes confirmed immediately.
- `manual`: booking stays pending until an administrator confirms it.

Allowed transitions must be explicit and covered by tests. Invalid transitions should return a clear error instead of silently changing data.

## 10. Notifications

Notification types:

- Booking confirmation to customer.
- New booking notification to admin.
- Booking cancellation notification.
- Reminder before visit.
- Return-visit reminder after completed booking.
- System warning to owner/admin.

Default reminder:

- `reminder_before_minutes = 60`.
- When a booking is created, the system creates a `notification_job` for `booking_start - reminder_before_minutes`.
- If the booking is created less than 60 minutes before start but at least 15 minutes before start, the reminder may be sent immediately.
- If the booking is created less than 15 minutes before start, the separate reminder is skipped to avoid noise.

Return-visit reminder:

- Sent after a configured number of days following a completed booking.
- It is included in MVP.
- Full promotional broadcasting and segmentation are postponed until after MVP.

Notification jobs must support retry when Telegram API is temporarily unavailable.

## 11. Input Validation

Validation must protect both Telegram customer input and admin configuration.

Customer fields:

- Name: required, trimmed, 2-80 characters.
- Phone: accepts common Russian formats such as `+7...` and `8...`, with spaces, brackets, and dashes allowed before normalization. Stored as normalized `+7XXXXXXXXXX` where possible.
- Vehicle plate: required, trimmed, uppercased, 2-15 characters. Validation is intentionally soft: letters, digits, spaces, and hyphens are allowed.

Admin settings:

- Price: non-negative money value.
- Duration: positive minutes, preferably divisible by 5 or 10, with an upper bound such as 480 minutes for MVP.
- Bay count: integer from 1 to 20.
- Working hours: start time must be before end time.
- Reminder delay: 0-1440 minutes or disabled.
- Return-visit delay: positive number of days or disabled.
- Comments and message texts: length-limited.

Invalid input must not reset the booking flow. The bot asks the user to correct the current field.

Example phone message:

> This does not look like a phone number. Please send it in the format +7XXXXXXXXXX.

Example plate message:

> I cannot recognize the plate number. Please enter letters and digits, for example A123BC154.

## 12. Error Handling

Expected failures should produce clear user-facing messages.

Cases:

- No available slots: offer another date or changing services.
- Slot became unavailable: offer another time or service changes.
- Invalid phone or plate: ask to correct only that field.
- Non-admin attempts admin action: deny with a short message.
- Admin tries to modify outdated booking state: show current booking state.
- Telegram API failure: retry notification job.
- Database or system failure: log structured error and notify owner/admin when appropriate.

Errors should not expose tokens, database details, tracebacks, or internal IDs to customers.

## 13. QA Strategy

Testing is a first-class part of this project. The system handles real customer bookings, so preventing failures is more important than moving quickly without confidence.

Testing will follow risk-based prioritization:

- Scheduling and overlap prevention.
- Bay capacity.
- Concurrent booking attempts.
- Booking status transitions.
- Reminders and notification jobs.
- User input validation.
- Admin permissions.
- PostgreSQL persistence and migrations.

Test levels:

- Unit tests for pure domain rules, validation, duration calculation, interval overlap, status transitions.
- Integration tests for services with PostgreSQL, booking creation, blocked slots, notification jobs, and transactions.
- API tests for FastAPI endpoints through TestClient or async HTTPX.
- Bot flow tests for Telegram handlers using fake updates/events without real Telegram API calls.
- End-to-end smoke tests for the core flow: choose service, choose slot, enter data, create booking, notify admin.
- Regression tests for every discovered bug.
- Manual acceptance checklist before release.

QA techniques:

- Boundary value analysis for time, duration, bay count, input lengths, reminder delay.
- Equivalence partitioning for valid and invalid phones, plates, working hours, and service values.
- Decision table testing for booking status actions and permissions.
- State transition testing for booking lifecycle.
- Parametrized tests for service/add-on combinations, capacities, and statuses.
- Concurrency tests for simultaneous attempts to book the last available slot.
- Negative tests for invalid data, occupied slots, expired cancellation, and unauthorized admin actions.

Development rule:

- Important business logic should be implemented with TDD.
- Write the failing test first, confirm it fails for the expected reason, then implement the minimal code.
- Bugs must be reproduced by a failing test before fixing.

Release quality gate:

- `pytest` passes.
- `ruff check` passes.
- `ruff format --check` passes.
- Type checking passes for core modules.
- Alembic migrations apply to a clean database.
- Docker Compose starts the stack.
- Core booking smoke scenario passes.
- No real Telegram tokens or secrets are committed.

## 14. Code Quality And Maintainability

Python code style:

- Follow PEP 8.
- Use PEP 257 docstrings for public services, complex scheduling rules, and non-trivial validators.
- Use PEP 484 type hints for public functions, service methods, DTOs/schemas, and repositories.
- Use Ruff for formatting, import sorting, and linting.
- Use mypy or pyright for static checks on core modules.

Class rules:

- Use a class when there is state, dependencies, or a clear role, such as `BookingService`, `SlotService`, or `NotificationService`.
- Do not create classes that only group static functions.
- One class should have one responsibility.
- SQLAlchemy models store data and relationships; they should not contain complex business workflows.
- Telegram handlers must stay thin and delegate to services.
- FastAPI routes must stay thin and delegate to services.
- Domain functions should remain easy to test without Telegram or database setup.

Database rules:

- Use SQLAlchemy 2.x typed mappings: `Mapped[...]` and `mapped_column`.
- Schema changes go through Alembic migrations.
- Use foreign keys, unique constraints, and check constraints where they protect data integrity.
- Booking creation must use transactions and re-check availability before insert.

Bot rules:

- Keep message texts and keyboard builders separated from handler logic.
- Name FSM states clearly, for example `BookingFlow.waiting_for_phone`.
- External Telegram sending should be isolated behind an adapter so tests do not call the real Telegram API.

Future frontend rules:

- MVP has no web panel, so BEM does not affect backend implementation.
- If a custom CSS web panel is added later, use BEM naming:
  - `block-name`
  - `block-name__element`
  - `block-name_modifier`
- Avoid elements of elements such as `block__elem__subelem`.
- Avoid CSS by `id`.
- Use semantic and stable class names.

## 15. Security And Privacy Notes

The system stores personal data: names, phone numbers, Telegram IDs, and vehicle plate numbers.

Required design constraints:

- Store secrets only in environment variables or secret management, never in git.
- Restrict admin actions by Telegram ID and car wash access.
- Do not expose personal data to unauthorized users.
- Log enough for debugging, but avoid logging sensitive tokens or full personal data unnecessarily.
- Prepare for privacy policy and personal data consent before production use.
- Provide data export and later data deletion support.

## 16. Acceptance Criteria

The MVP is ready when:

- A customer can complete a booking in Telegram.
- The system shows only slots that fully fit selected services and add-ons.
- The system prevents double-booking and capacity overflow.
- The system repeats availability checks before saving a booking.
- Administrator receives new booking notifications.
- Administrator can view, confirm, cancel, complete, and mark no-show bookings.
- Owner/admin can configure services, prices, durations, working hours, bay count, confirmation mode, reminder timing, and admin IDs.
- The default reminder is created one hour before the booking.
- Return-visit reminder is created after completed bookings.
- Validation handles invalid customer and admin input without breaking the flow.
- The stack runs locally and on VPS through Docker Compose.
- The automated quality gate passes.

## 17. Post-MVP Deferred Features

- Full web admin panel.
- Full promotional broadcasting and segmentation.
- Long-running detailing, dry cleaning, polishing, ceramic coating, and protection packages.
- Online payments or deposits.
- Loyalty program.
- Multiple separate Telegram bots for multiple car washes.
- Advanced bay-specific scheduling.
- Analytics dashboard.
- CRM/accounting/map integrations.
- MAX platform support.

