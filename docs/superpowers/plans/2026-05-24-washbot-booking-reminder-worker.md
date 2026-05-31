# WashBot Booking Reminder Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate worker process that delivers due booking reminders to customers in Telegram for confirmed bookings.

**Architecture:** Keep reminder delivery outside Telegram update handlers. Reuse `notification_jobs` as the durable queue, add repository helpers for due job claim/finalization, and implement a small worker loop that calls a reminder delivery service.

**Tech Stack:** Python 3.12, aiogram, SQLAlchemy async ORM, pytest, ruff, mypy.

---

### Task 1: Add Reminder Job Repository Operations

**Files:**
- Modify: `app/db/repositories.py`
- Test: `tests/db/test_booking_repositories.py`

- [ ] **Step 1: Write failing repository tests for due job selection and status updates**

Add tests that verify:
- only due `booking_reminder` jobs with `pending` status are selected;
- stale `processing` jobs older than reclaim timeout are selected;
- finalization updates (`sent`, `skipped`, `failed`) persist status and attempts.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/db/test_booking_repositories.py -k notification -v`
Expected: FAIL with missing repository functions.

- [ ] **Step 3: Implement minimal repository functions**

Add functions in `app/db/repositories.py`:
- `list_due_reminder_jobs(...)`
- `claim_notification_job(...)`
- `mark_notification_job_sent(...)`
- `mark_notification_job_skipped(...)`
- `mark_notification_job_failed(...)`

Use conditional `update(...)` for safe claim (`pending -> processing`) and a reclaim path for stale `processing`.

- [ ] **Step 4: Run repository tests**

Run: `pytest tests/db/test_booking_repositories.py -k notification -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/db/repositories.py tests/db/test_booking_repositories.py
git commit -m "feat: add reminder job repository operations"
```

### Task 2: Add Reminder Delivery Service

**Files:**
- Create: `app/services/reminder_delivery.py`
- Modify: `app/db/repositories.py`
- Test: `tests/services/test_reminder_delivery.py`

- [ ] **Step 1: Write failing service tests**

Add tests for outcomes:
- confirmed future booking + linked Telegram user -> `sent`;
- pending/cancelled/past booking -> `skipped`;
- missing linked user -> `skipped`;
- Telegram send error -> `failed` and attempts increment.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/services/test_reminder_delivery.py -v`
Expected: FAIL because service module does not exist.

- [ ] **Step 3: Implement delivery service**

Create `ReminderDeliveryService` with method like:
- `process_job(job_id: int, now: datetime) -> DeliveryOutcome`

Service responsibilities:
- load reminder context (job + booking + customer + user);
- validate send conditions from spec;
- send Telegram message via bot client adapter;
- finalize job status via repository methods.

- [ ] **Step 4: Run service tests**

Run: `pytest tests/services/test_reminder_delivery.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/reminder_delivery.py app/db/repositories.py tests/services/test_reminder_delivery.py
git commit -m "feat: add reminder delivery service"
```

### Task 3: Add Reminder Message Formatter

**Files:**
- Modify: `app/bot/customer_booking/messages.py`
- Modify: `tests/bot/customer_booking/test_messages.py`

- [ ] **Step 1: Write failing message test**

Add a test asserting reminder text format:
- contains booking date and time;
- contains cancellation hint;
- uses stable Russian wording agreed in spec.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/bot/customer_booking/test_messages.py -k reminder -v`
Expected: FAIL with missing formatter.

- [ ] **Step 3: Implement formatter**

Add a pure helper function, for example:
- `format_booking_reminder_text(start_at: datetime) -> str`

- [ ] **Step 4: Run message tests**

Run: `pytest tests/bot/customer_booking/test_messages.py -k reminder -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/bot/customer_booking/messages.py tests/bot/customer_booking/test_messages.py
git commit -m "feat: add booking reminder message formatter"
```

### Task 4: Add Worker Runtime And Processing Loop

**Files:**
- Create: `app/worker/__init__.py`
- Create: `app/worker/main.py`
- Create: `app/worker/reminders.py`
- Modify: `README.md`
- Test: `tests/test_worker_reminders.py`

- [ ] **Step 1: Write failing worker loop tests**

Add tests covering:
- due valid job processed to `sent`;
- invalid job processed to `skipped`;
- failed send processed to `failed`;
- one job failure does not crash the whole cycle.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_worker_reminders.py -v`
Expected: FAIL because worker modules do not exist.

- [ ] **Step 3: Implement worker modules**

Implement:
- poll interval loop;
- one-cycle function for testability;
- due job fetch, claim, process, finalize;
- logging for per-job errors and loop continuation.

- [ ] **Step 4: Document local run commands**

Update `README.md` with:
- `python -m app.bot.main`
- `python -m app.worker.main`

- [ ] **Step 5: Run worker tests**

Run: `pytest tests/test_worker_reminders.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/worker app/README.md README.md tests/test_worker_reminders.py
git commit -m "feat: add booking reminder worker runtime"
```

### Task 5: End-to-End Verification For Reminder Feature

**Files:**
- Modify: `tests/services/test_customer_booking.py`
- Modify: `tests/test_demo_seed.py` (if needed for strict assumptions)

- [ ] **Step 1: Add integration-style scenario test**

Ensure:
- booking creates reminder job;
- admin confirms booking;
- worker sends reminder and marks `sent`.

- [ ] **Step 2: Run targeted test**

Run: `pytest tests/services/test_customer_booking.py -k reminder -v`
Expected: PASS.

- [ ] **Step 3: Run full quality gate**

Run:
- `pytest -q`
- `ruff check .`
- `ruff format --check .`
- `mypy app`

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/services/test_customer_booking.py tests/test_demo_seed.py
git commit -m "test: cover reminder worker end-to-end behavior"
```

## Plan Self-Review

1. Spec coverage:
- Separate worker process: Task 4.
- Confirmed-only reminder rule: Task 2.
- Skip invalid/outdated jobs: Tasks 1-2.
- Failed send behavior and attempts: Tasks 1-2.
- Stale processing reclaim: Task 1.
- Reminder message text: Task 3.
- Testing across repository/service/worker: Tasks 1, 2, 4, 5.

2. Placeholder scan:
- No `TODO`/`TBD`.
- Each task has concrete files, commands, and expected outcomes.

3. Type consistency:
- Uses existing project concepts (`NotificationJob`, statuses, async repository/service split).
- Keeps delivery logic in service layer and orchestration in worker layer.

