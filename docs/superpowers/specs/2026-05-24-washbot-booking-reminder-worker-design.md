# WashBot Booking Reminder Worker Design

## 1. Purpose

WashBot already creates `notification_jobs` for booking reminders when a customer booking is
saved. The missing part is delivery: a background process must pick due reminder jobs, decide
whether they are still valid, and send a Telegram message to the customer.

The MVP goal is a reliable reminder loop without adding heavy infrastructure such as Redis,
Celery, or an external queue service.

## 2. Scope

Included:

- Add a separate background `worker` process.
- Poll due `notification_jobs` on a short interval.
- Send booking reminder messages to customers in Telegram.
- Send reminders only for `confirmed` bookings.
- Close jobs that are no longer valid for delivery.
- Record final job status and attempt count.
- Make processing safe across worker restarts.
- Cover worker behavior with service and integration-style tests.

Not included:

- Return-visit reminders.
- Promotional messaging.
- Multi-step retry policies or exponential backoff.
- Dead-letter queues.
- External schedulers or queue brokers.
- Owner-facing reminder settings UI.

## 3. Recommended Architecture

Use a separate lightweight worker process that runs alongside the Telegram bot.

Recommended shape:

- `app/worker/main.py`: process entrypoint and polling loop.
- `app/worker/reminders.py`: reminder job processor.
- `app/services/reminder_delivery.py`: application service that loads job context,
  evaluates whether a reminder should be sent, and returns a delivery outcome.
- `app/bot/customer_booking/messages.py` or a nearby focused message helper:
  reminder text formatter.

This keeps Telegram booking handlers focused on interactive flows and keeps reminder delivery
independent from whether the bot is currently handling a user update.

## 4. Why This Approach

### Option 1: Separate worker process

Recommended.

Pros:

- reminders do not depend on an active chat update;
- worker can be restarted independently from the bot;
- architecture matches the existing technical design;
- easier to integrate with production process management.

Cons:

- one more process to run locally and on the server.

### Option 2: Background loop inside the bot process

Pros:

- fewer files and less setup.

Cons:

- reminders stop when the bot process stops;
- harder to reason about lifecycle and restart behavior;
- less production-friendly.

### Option 3: External cron calling a one-shot command

Pros:

- operationally simple on some servers.

Cons:

- less convenient for local development;
- splits scheduling logic between app code and server config.

## 5. Delivery Rules

The worker scans jobs where:

- `kind == "booking_reminder"`;
- `status == "pending"` or stale `processing`;
- `run_at <= now`.

For each due job, the worker loads the linked booking, customer, and Telegram user.

A reminder is sent only when all conditions are true:

- the booking exists;
- the booking status is `confirmed`;
- the booking start time is still in the future;
- the customer is linked to a `users` record with a Telegram ID.

If any of these checks fail, the job is not retried and is closed as `skipped`.

## 6. Job Lifecycle

Existing `notification_jobs` fields already support a simple lifecycle:

- `pending`: waiting for processing;
- `processing`: currently claimed by a worker;
- `sent`: reminder delivered successfully;
- `skipped`: intentionally closed without sending;
- `failed`: send attempt failed.

Worker claim flow:

1. read a batch of due jobs;
2. atomically move each selected job from `pending` to `processing`;
3. process one job at a time;
4. finalize to `sent`, `skipped`, or `failed`.

To recover from crashes, stale `processing` jobs should become eligible again after a timeout.
For MVP, use a conservative rule:

- a `processing` reminder job older than 5 minutes may be reclaimed.

This requires the worker to treat `processing` jobs with `run_at <= now` and enough age as
recoverable work.

## 7. Telegram Reminder Message

The reminder should be concise and operational:

```text
Напоминание: вы записаны на автомойку 30.05.2026 в 19:00.
Если планы изменились, откройте бота и отмените запись заранее.
```

MVP reminder message characteristics:

- no inline buttons;
- no admin details;
- no duplicated service breakdown in MVP;
- enough context for the customer to recognize the visit time.

## 8. Error Handling

Expected non-send outcomes:

- booking is `pending`, cancelled, completed, or `no_show` -> `skipped`;
- booking start time is already in the past -> `skipped`;
- no linked Telegram user -> `skipped`;
- booking was deleted or is inaccessible -> `skipped`.

Telegram/API failure:

- increment `attempts`;
- set status to `failed`;
- do not crash the whole worker loop.

Unexpected code or database failure while processing one job:

- the job should not be reported as `sent`;
- the worker should log the failure and continue with the next polling cycle.

For MVP, there is no advanced retry scheduler. A failed job stays `failed` for operator review
or a future retry feature.

## 9. Repository And Service Responsibilities

Repository layer should provide focused helpers for:

- selecting due reminder jobs;
- conditionally claiming a job for processing;
- loading reminder context: job, booking, customer, user;
- marking a job as `sent`, `skipped`, or `failed`;
- incrementing attempts safely.

Application service should decide the delivery outcome, not raw handlers or the polling loop.

Suggested delivery outcomes:

- `sent`
- `skipped`
- `failed`

The worker loop should orchestrate polling and logging, while business rules stay in the
service layer.

## 10. Local And Production Operation

Local demo target operation uses two long-lived processes:

- `python -m app.bot.main`
- `python -m app.worker.main`

Production should run them as separate managed services under the same environment settings.

The worker loop can use a fixed poll interval for MVP, such as 30 or 60 seconds.

## 11. Testing Strategy

Repository tests:

- select only due reminder jobs;
- do not select future jobs;
- reclaim stale `processing` jobs after timeout;
- final status updates persist correctly.

Service tests:

- confirmed future booking with Telegram user sends reminder;
- pending booking is skipped;
- cancelled booking is skipped;
- past booking is skipped;
- missing Telegram user is skipped;
- Telegram send failure marks job as `failed` and increments attempts.

Worker loop tests:

- one due job is claimed and finalized as `sent`;
- one invalid job is finalized as `skipped`;
- one failed send becomes `failed`;
- one broken job does not stop the next polling cycle.

Quality gate:

- `pytest -q`
- `ruff check .`
- `ruff format --check .`
- `mypy app`

## 12. Acceptance Criteria

This feature is complete when:

- due booking reminder jobs are processed by a separate worker process;
- only `confirmed` bookings generate reminder messages;
- invalid or outdated reminder jobs are closed as `skipped`;
- send failures become `failed` and increase `attempts`;
- worker restart can recover stale `processing` jobs;
- the reminder message is delivered to the correct Telegram user for confirmed bookings;
- tests cover repository selection, service rules, and worker processing behavior.

## Self-Review

- Placeholder scan: no `TBD`, `TODO`, or vague "later in this same feature" steps remain.
- Internal consistency: only `confirmed` bookings send reminders; all other booking states are
  explicitly non-send paths.
- Scope check: this is focused on one subsystem, the booking reminder worker.
- Ambiguity check: failed sends are terminal for MVP; retries are intentionally postponed.
