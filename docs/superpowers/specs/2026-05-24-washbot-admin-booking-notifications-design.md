# WashBot Admin Booking Notifications And Today View Design

## 1. Purpose

This feature connects the completed customer booking flow to daily car wash operations.
When a customer creates a booking, administrators must see it in Telegram and be able to
open today's bookings without using a database or developer tools.

The MVP goal is not a full admin panel. It is the minimum reliable admin loop:

- notify admins about a new booking;
- show today's bookings;
- allow basic status actions from Telegram.

## 2. Scope

Included:

- Configure administrator Telegram IDs through environment settings.
- Keep the code ready for later migration to the `admins` table.
- Send a new-booking notification to configured admins after customer booking creation.
- Show a concise booking summary to admins.
- Add admin inline buttons:
  - `Подтвердить` for `pending` bookings;
  - `Отменить`;
  - `Сегодня`.
- Show today's bookings to admins.
- Restrict admin actions to configured admin Telegram IDs.
- Handle stale booking state by showing the current state instead of blindly changing it.

Not included:

- Full admin settings menu.
- Manual booking creation.
- Time blocking.
- Editing services or prices.
- Admin notification retry worker.
- Web admin panel.

## 3. Admin Source

For the first MVP release, administrator Telegram IDs come from settings:

```env
ADMIN_TELEGRAM_IDS=123456789,987654321
```

The implementation should parse this into a list or set of integer Telegram IDs.

The permission boundary should be isolated behind an admin access helper or service method.
That helper may initially use settings, but its interface should allow replacing the source
with the `admins` database table later.

## 4. New Booking Notification Flow

After a booking is successfully created by the customer flow:

1. The customer still receives their normal confirmation or pending message.
2. The bot sends each configured admin a new-booking notification.
3. The notification includes:
   - date and time;
   - booking status;
   - selected services;
   - total duration;
   - total price;
   - customer name;
   - customer phone;
   - vehicle plate.
4. The notification includes action buttons:
   - `Подтвердить` only when status is `pending`;
   - `Отменить`;
   - `Сегодня`.

If admin notification sending fails, the customer booking must remain created.
The failure should not expose Telegram API details to the customer.
For this feature, tests should verify that notification errors do not undo booking creation.
Durable retry is left for the later worker/notification feature.

## 5. Today View

Admins can open today's bookings from:

- the `Сегодня` button under a notification;
- a dedicated admin callback or command if useful for testability.

The today view shows bookings for the configured default car wash and branch for the current date.

The list should include active operational statuses:

- `pending`;
- `confirmed`.

Cancelled, completed, and no-show bookings should not be shown in the default today list.
They can be added later in a more complete admin view.

If there are no bookings today, the bot replies:

```text
Сегодня записей нет.
```

## 6. Admin Actions

### Confirm

Confirm is available only for `pending` bookings.

When an admin presses `Подтвердить`:

- if the booking is still `pending`, status changes to `confirmed`;
- if the booking already changed, the bot shows the current status;
- non-admin users receive `Недостаточно прав.`

### Cancel

Cancel is available for `pending` and `confirmed` bookings.

When an admin presses `Отменить`:

- if the booking is still active, status changes to `cancelled_by_admin`;
- if the booking already changed, the bot shows the current status;
- non-admin users receive `Недостаточно прав.`

The system should use explicit booking status transition rules from the domain layer.
Handlers must not write booking statuses directly.

## 7. Callback Design

Callbacks should be stable and short:

- `admin:today`
- `admin:confirm:<booking_id>`
- `admin:cancel:<booking_id>`

Parsers should validate prefixes and return typed booking IDs.
Invalid callback data should not silently operate on the wrong booking.

## 8. Service Layer Design

Add an admin-facing service or focused methods that do not depend on aiogram:

- list today's bookings for a car wash/branch/date;
- get one booking with selected services and customer details;
- confirm booking by ID;
- cancel booking by ID;
- check whether a Telegram user is allowed to perform admin actions.

Status changes should be conditional:

- confirming should only update `pending` to `confirmed`;
- admin cancellation should only update `pending` or `confirmed` to `cancelled_by_admin`;
- stale state should return current booking status instead of pretending the action succeeded.

The service should use existing domain status transition rules.

## 9. Bot Layer Design

Create a separate admin booking package under `app/bot/admin_bookings` or similarly focused files.

Recommended files:

- `callbacks.py`: callback constants/builders/parsers.
- `messages.py`: admin-facing Russian texts and formatters.
- `keyboards.py`: admin action keyboards.
- `handlers.py`: aiogram router for admin callbacks.

The dispatcher should include both customer and admin routers.

The customer booking confirmation handler may call an admin notifier adapter after successful booking creation.
To keep tests simple and avoid real Telegram API calls, the notifier should be isolated behind a small object/function
that can be faked in handler tests.

## 10. Error Handling

Expected failures:

- non-admin action: `Недостаточно прав.`;
- booking not found or no longer belongs to this car wash: show a short current-state/error message;
- stale status: show current status and avoid invalid transition;
- no bookings today: show empty-state message.

Unexpected failures:

- database or programming errors should not be swallowed as successful admin actions;
- Telegram sending errors for admin notifications should not break customer booking creation;
- internal exception text must not be sent to customers or admins.

## 11. Testing Strategy

Settings tests:

- parse `ADMIN_TELEGRAM_IDS`;
- empty value gives no admins;
- invalid values fail settings validation or are rejected clearly.

Service tests:

- list today's pending/confirmed bookings;
- ignore cancelled/completed/no-show in today view;
- confirm pending booking;
- refuse confirm for non-pending booking and return current status;
- cancel pending/confirmed booking;
- refuse cancel for terminal statuses and return current status;
- enforce car wash/branch ownership.

Bot tests:

- admin notification message contains booking details and correct buttons;
- pending booking notification includes `Подтвердить`;
- confirmed booking notification does not include `Подтвердить`;
- today callback shows list for admin;
- today callback denies non-admin;
- confirm callback changes pending booking for admin;
- cancel callback changes active booking for admin;
- stale callback shows current state;
- customer booking still succeeds if admin notification send fails.

Quality gate:

- `pytest -q`
- `ruff check .`
- `ruff format --check .`
- `mypy app`

## 12. Acceptance Criteria

This feature is complete when:

- configured admins receive a Telegram notification after new booking creation;
- admin notification includes useful booking details and action buttons;
- admin can open today's active bookings;
- admin can confirm pending bookings;
- admin can cancel pending/confirmed bookings;
- non-admin users cannot perform admin actions;
- stale admin callbacks do not corrupt booking state;
- admin notification failures do not undo customer booking creation;
- tests cover service rules and bot handler behavior.

## Self-Review

- Placeholder scan: no `TBD`, `TODO`, or vague future-only implementation steps remain.
- Scope check: focused on notification, today view, confirm, and cancel only.
- Consistency check: admin IDs start in settings but permission logic is isolated for later database-backed admins.
- Ambiguity check: today view includes only `pending` and `confirmed` by default.
