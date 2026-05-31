from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Booking, Branch, CarWash, Customer, NotificationJob, User
from app.worker.reminders import process_due_reminder_jobs


@dataclass(frozen=True, slots=True)
class ReminderSeed:
    job_id: int
    telegram_id: int | None


class FakeReminderGateway:
    def __init__(self, *, failing_telegram_ids: set[int] | None = None) -> None:
        self.failing_telegram_ids = failing_telegram_ids or set()
        self.calls: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        if telegram_id in self.failing_telegram_ids:
            raise RuntimeError("telegram unavailable")
        self.calls.append((telegram_id, text))


async def seed_reminder_job(
    db_session: AsyncSession,
    *,
    now: datetime,
    booking_status: str = "confirmed",
    start_at: datetime | None = None,
    telegram_id: int | None = 123456789,
    job_status: str = "pending",
    job_kind: str = "booking_reminder",
    run_at: datetime | None = None,
    claimed_at: datetime | None = None,
) -> ReminderSeed:
    start_at = start_at or (now + timedelta(hours=1))
    run_at = run_at or now

    car_wash = CarWash(name="Wash", confirmation_mode="manual", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()

    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()

    user = None
    if telegram_id is not None:
        user = User(telegram_id=telegram_id, username="client")
        db_session.add(user)
        await db_session.flush()

    customer = Customer(
        car_wash_id=car_wash.id,
        user_id=user.id if user is not None else None,
        name="Ivan",
        phone="+79990000000",
        vehicle_plate="A123AA154",
    )
    db_session.add(customer)
    await db_session.flush()

    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1),
        status=booking_status,
    )
    db_session.add(booking)
    await db_session.flush()

    job = NotificationJob(
        car_wash_id=car_wash.id,
        booking_id=booking.id,
        kind=job_kind,
        run_at=run_at,
        claimed_at=claimed_at,
        status=job_status,
        attempts=0,
    )
    db_session.add(job)
    await db_session.commit()

    return ReminderSeed(job_id=job.id, telegram_id=telegram_id)


async def load_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    job_id: int,
) -> NotificationJob:
    async with sessionmaker() as session:
        job = await session.get(NotificationJob, job_id)
        assert job is not None
        return job


@pytest.fixture
def db_sessionmaker(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_session.bind, expire_on_commit=False)


async def test_process_due_reminder_jobs_sends_due_confirmed_booking(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_job(db_session, now=now)
    gateway = FakeReminderGateway()

    result = await process_due_reminder_jobs(db_sessionmaker, gateway, now=now)

    assert result.sent == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert gateway.calls == [(123456789, gateway.calls[0][1])]
    assert "24.05.2026" in gateway.calls[0][1]
    job = await load_job(db_sessionmaker, seed.job_id)
    assert job.status == "sent"
    assert job.attempts == 1
    assert job.claimed_at is None


async def test_process_due_reminder_jobs_skips_invalid_booking(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_job(db_session, now=now, booking_status="pending")
    gateway = FakeReminderGateway()

    result = await process_due_reminder_jobs(db_sessionmaker, gateway, now=now)

    assert result.sent == 0
    assert result.skipped == 1
    assert result.failed == 0
    assert gateway.calls == []
    job = await load_job(db_sessionmaker, seed.job_id)
    assert job.status == "skipped"
    assert job.attempts == 1


async def test_process_due_reminder_jobs_marks_failed_send(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_job(db_session, now=now, telegram_id=111)
    gateway = FakeReminderGateway(failing_telegram_ids={111})

    result = await process_due_reminder_jobs(db_sessionmaker, gateway, now=now)

    assert result.sent == 0
    assert result.skipped == 0
    assert result.failed == 1
    assert gateway.calls == []
    job = await load_job(db_sessionmaker, seed.job_id)
    assert job.status == "failed"
    assert job.attempts == 1


async def test_process_due_reminder_jobs_continues_after_one_job_fails(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    failed_seed = await seed_reminder_job(db_session, now=now, telegram_id=111)
    sent_seed = await seed_reminder_job(db_session, now=now, telegram_id=222)
    gateway = FakeReminderGateway(failing_telegram_ids={111})

    result = await process_due_reminder_jobs(db_sessionmaker, gateway, now=now)

    assert result.sent == 1
    assert result.failed == 1
    assert gateway.calls == [(222, gateway.calls[0][1])]
    failed_job = await load_job(db_sessionmaker, failed_seed.job_id)
    sent_job = await load_job(db_sessionmaker, sent_seed.job_id)
    assert failed_job.status == "failed"
    assert sent_job.status == "sent"
