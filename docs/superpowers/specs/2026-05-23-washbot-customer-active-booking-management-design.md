# WashBot Customer Active Booking Management Design

## 1. Purpose

This feature completes the customer self-service loop after booking creation.
The customer must be able to open the bot, view their current future booking,
and cancel it when cancellation is still allowed.

For the MVP, each Telegram customer can have only one active future booking at a time.
This keeps the customer flow simple and avoids list-management UI before the first release.

## 2. Scope

Included:

- Show a customer their active future booking.
- Allow customer cancellation from Telegram.
- Block customer cancellation when less than 60 minutes remain before booking start.
- Mark cancelled bookings as `cancelled_by_customer`.
- Free the slot by changing booking status.
- Add tests for service rules and Telegram handler behavior.

Not included:

- Admin-side cancellation.
- Rescheduling in one step.
- Multiple active bookings per customer.
- Admin notification delivery for cancellation.
- Web admin panel changes.

## 3. Product Rules

An active customer booking is:

- linked to the current Telegram user/customer;
- scheduled in the future;
- in status `pending` or `confirmed`.

MVP rule:

- one customer can have at most one active future booking.

Cancellation rule:

- customer cancellation is allowed when booking start is at least 60 minutes away;
- customer cancellation is denied when less than 60 minutes remain;
- denied cancellation does not change booking status.

If the customer has no active booking, the bot shows a short empty-state message.

If the booking was already cancelled, completed, marked no-show, or otherwise no longer active,
the bot treats it as no active booking for the customer view.

## 4. Customer Telegram Flow

The `/start` screen should offer two customer actions:

- `Записаться`
- `Моя запись`

When the customer presses `Моя запись`:

1. The bot resolves the Telegram user to the stored customer identity.
2. The bot asks the application service for the active future booking.
3. If no booking exists, the bot replies: `У вас нет активной записи.`
4. If a booking exists, the bot shows a summary with date, time, status, vehicle plate,
   selected services, total duration, and total price.
5. The bot includes the `Отменить запись` action.

When the customer presses `Отменить запись`:

1. The bot re-checks the active future booking.
2. If there is no active booking, the bot replies with the empty-state message.
3. If less than 60 minutes remain before start, the bot replies:
   `Отменить запись уже нельзя. Свяжитесь с администратором.`
4. If cancellation is allowed, the service changes status to `cancelled_by_customer`
   and the bot replies: `Запись отменена.`

The bot must not trust a stale callback as proof that a booking can still be cancelled.
The service always reloads the current booking state before changing status.

## 5. Service Layer Design

Add customer-facing methods to `CustomerBookingService` or a focused companion service
if the existing class becomes too broad.

Required service behavior:

- find the latest active future booking for a Telegram user/customer;
- return enough data to render the customer-facing summary;
- cancel the active booking if cancellation is allowed;
- raise an expected domain error when cancellation is too late;
- return an empty result when no active booking exists.

The service should not depend on aiogram or Telegram message types.

Time comparisons should use an injectable `now` value in tests or a small clock boundary
so the 60-minute cancellation rule is deterministic.

## 6. Data And Repository Needs

The feature can use existing tables:

- `users`
- `customers`
- `bookings`
- `booking_services`
- `services`

Repository helpers may be added for:

- finding a customer by Telegram user ID;
- loading one active future booking with selected services;
- updating booking status to `cancelled_by_customer`.

The active-booking query must filter by status and future start time.
It must not return cancelled, completed, or no-show bookings.

## 7. Message And Keyboard Design

New callback actions:

- `book:my_active`
- `book:cancel_active`

New user-facing texts:

- `У вас нет активной записи.`
- `Отменить запись уже нельзя. Свяжитесь с администратором.`
- `Запись отменена.`

Booking summary should reuse the existing formatting style where possible.
Dynamic service names and customer fields must remain HTML-safe because the bot uses HTML parse mode.

## 8. Error Handling

Expected failures:

- no active booking: show empty-state message;
- cancellation too late: show late-cancellation message;
- booking changed between view and cancel: reload state and show the correct current message.

Unexpected failures:

- database or programming errors should not be swallowed as successful cancellation;
- internal exception text must not be shown to the customer.

## 9. Testing Strategy

Service tests:

- active future `pending` booking is returned;
- active future `confirmed` booking is returned;
- cancelled/completed/no-show bookings are ignored;
- past bookings are ignored;
- cancellation changes status to `cancelled_by_customer`;
- cancellation less than 60 minutes before start is rejected;
- cancellation exactly 60 minutes before start is allowed;
- no active booking returns an empty result.

Bot handler tests:

- `/start` includes both booking and active-booking actions;
- pressing `Моя запись` with no booking shows the empty-state message;
- pressing `Моя запись` with a booking shows summary and cancel button;
- pressing `Отменить запись` successfully cancels and clears the active action;
- pressing `Отменить запись` too late shows the late-cancellation message;
- stale cancel callback with no active booking shows the empty-state message.

Quality gate:

- `pytest -q`
- `ruff check .`
- `ruff format --check .`
- `mypy app`

## 10. Acceptance Criteria

This feature is complete when:

- a customer can view their one active future booking in Telegram;
- a customer can cancel it when at least 60 minutes remain;
- cancellation is blocked when less than 60 minutes remain;
- cancelled bookings no longer occupy capacity;
- the bot does not crash on stale active-booking callbacks;
- service and bot tests cover the business rules.

## Self-Review

- Placeholder scan: no `TBD` or unspecified implementation steps remain.
- Scope check: focused on customer active-booking view and cancellation only.
- Consistency check: cancellation uses existing booking status `cancelled_by_customer`
  and does not introduce multi-booking UI.
- Ambiguity check: the cancellation boundary is explicit:
  exactly 60 minutes before start is allowed, less than 60 minutes is denied.
