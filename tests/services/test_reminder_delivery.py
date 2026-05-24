from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Booking, Branch, CarWash, Customer, NotificationJob, User
from app.services.reminder_delivery import ReminderDeliveryService


@dataclass
class ReminderSeed:
    booking: Booking
    customer: Customer
    job: NotificationJob
    user: User | None


class FakeTelegramGateway:
    def __init__(
        self,
        *,
        should_fail: bool = False,
        before_send: object | None = None,
    ) -> None:
        self.should_fail = should_fail
        self.before_send = before_send
        self.calls: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        if self.before_send is not None:
            await self.before_send()
        if self.should_fail:
            raise RuntimeError("telegram unavailable")
        self.calls.append((telegram_id, text))


async def load_job(db_session: AsyncSession, job_id: int) -> NotificationJob:
    return await db_session.get(NotificationJob, job_id)


async def seed_reminder_context(
    db_session: AsyncSession,
    *,
    booking_status: str = "confirmed",
    start_at: datetime | None = None,
    with_linked_user: bool = True,
    attempts: int = 0,
    job_kind: str = "booking_reminder",
    job_status: str = "processing",
    claimed_at: datetime | None = None,
) -> ReminderSeed:
    now = datetime(2026, 5, 24, 12, 0)
    start_at = start_at or (now + timedelta(hours=2))
    claimed_at = now if claimed_at is None else claimed_at

    car_wash = CarWash(name="Wash", confirmation_mode="manual", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()

    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()

    user = None
    if with_linked_user:
        user = User(telegram_id=123456789, username="client")
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
        run_at=start_at - timedelta(hours=1),
        claimed_at=claimed_at,
        status=job_status,
        attempts=attempts,
    )
    db_session.add(job)
    await db_session.commit()

    return ReminderSeed(booking=booking, customer=customer, job=job, user=user)


async def test_process_job_sends_reminder_for_confirmed_future_booking(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session)
    gateway = FakeTelegramGateway()

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "sent"
    assert len(gateway.calls) == 1
    assert gateway.calls[0][0] == 123456789
    assert "24.05.2026" in gateway.calls[0][1]
    assert "14:00" in gateway.calls[0][1]
    job = await load_job(db_session, seed.job.id)
    assert job.status == "sent"
    assert job.attempts == 1


async def test_process_job_skips_pending_booking(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, booking_status="pending")
    gateway = FakeTelegramGateway()

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "skipped"
    assert gateway.calls == []
    job = await load_job(db_session, seed.job.id)
    assert job.status == "skipped"
    assert job.attempts == 1


async def test_process_job_skips_cancelled_booking(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, booking_status="cancelled")
    gateway = FakeTelegramGateway()

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "skipped"
    assert gateway.calls == []
    job = await load_job(db_session, seed.job.id)
    assert job.status == "skipped"
    assert job.attempts == 1


async def test_process_job_skips_past_booking(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, start_at=now - timedelta(minutes=1))
    gateway = FakeTelegramGateway()

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "skipped"
    assert gateway.calls == []
    job = await load_job(db_session, seed.job.id)
    assert job.status == "skipped"
    assert job.attempts == 1


async def test_process_job_skips_when_customer_has_no_linked_user(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, with_linked_user=False)
    gateway = FakeTelegramGateway()

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "skipped"
    assert gateway.calls == []
    job = await load_job(db_session, seed.job.id)
    assert job.status == "skipped"
    assert job.attempts == 1


async def test_process_job_marks_failed_when_telegram_send_raises(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, attempts=2)
    gateway = FakeTelegramGateway(should_fail=True)

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "failed"
    assert gateway.calls == []
    job = await load_job(db_session, seed.job.id)
    assert job.status == "failed"
    assert job.attempts == 3


async def test_process_job_leaves_non_reminder_job_untouched(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, job_kind="return_visit")
    gateway = FakeTelegramGateway()

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "skipped"
    assert gateway.calls == []
    job = await load_job(db_session, seed.job.id)
    assert job.status == "processing"
    assert job.attempts == 0
    assert job.claimed_at == now


async def test_process_job_leaves_non_processing_job_untouched(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, job_status="pending")
    gateway = FakeTelegramGateway()

    outcome = await ReminderDeliveryService(db_session, gateway).process_job(seed.job.id, now=now)

    assert outcome == "skipped"
    assert gateway.calls == []
    job = await load_job(db_session, seed.job.id)
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.claimed_at == now


async def test_process_job_raises_on_claim_mismatch_during_finalization(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0)
    seed = await seed_reminder_context(db_session, claimed_at=now - timedelta(minutes=2))
    job_id = seed.job.id
    sessionmaker = async_sessionmaker(db_session.bind, expire_on_commit=False)

    async def reassign_claim() -> None:
        async with sessionmaker() as other_session:
            job = await load_job(other_session, job_id)
            job.claimed_at = now
            await other_session.commit()

    gateway = FakeTelegramGateway(before_send=reassign_claim)

    with pytest.raises(RuntimeError, match="concurrently"):
        await ReminderDeliveryService(db_session, gateway).process_job(job_id, now=now)

    reloaded_job = await load_job(db_session, job_id)
    assert reloaded_job.status == "processing"
    assert reloaded_job.attempts == 0
    assert reloaded_job.claimed_at == now
