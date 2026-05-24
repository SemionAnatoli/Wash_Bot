from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Booking,
    Branch,
    CarWash,
    Customer,
    NotificationJob,
    Service,
    User,
    WorkingHours,
)
from app.db.repositories import (
    claim_notification_job,
    get_branch,
    get_or_create_user,
    get_working_hours_for_weekday,
    list_active_addon_services,
    list_active_main_services,
    list_due_reminder_jobs,
    mark_notification_job_failed,
    mark_notification_job_sent,
    mark_notification_job_skipped,
)


async def test_service_repositories_split_main_services_and_addons(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    db_session.add_all(
        [
            Service(
                car_wash_id=car_wash.id,
                title="Body wash",
                category="wash",
                price=Decimal("500"),
                duration_minutes=30,
                is_addon=False,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Wax",
                category="addon",
                price=Decimal("200"),
                duration_minutes=15,
                is_addon=True,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Old package",
                category="wash",
                price=Decimal("1000"),
                duration_minutes=60,
                is_addon=False,
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    main_services = await list_active_main_services(db_session, car_wash_id=car_wash.id)
    addons = await list_active_addon_services(db_session, car_wash_id=car_wash.id)

    assert [service.title for service in main_services] == ["Body wash"]
    assert [service.title for service in addons] == ["Wax"]


async def test_branch_and_working_hours_repositories_return_config(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(
        car_wash_id=car_wash.id,
        title="Main",
        address="Street",
        bay_count=2,
    )
    db_session.add(branch)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(9),
            end_time=time(18),
        )
    )
    await db_session.commit()

    loaded_branch = await get_branch(db_session, car_wash_id=car_wash.id, branch_id=branch.id)
    hours = await get_working_hours_for_weekday(
        db_session,
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        weekday=0,
    )

    assert loaded_branch is not None
    assert loaded_branch.bay_count == 2
    assert hours is not None
    assert hours.start_time == time(9)
    assert hours.end_time == time(18)


async def test_get_or_create_user_recovers_from_unique_conflict(tmp_path) -> None:
    database_path = tmp_path / "get-or-create-user-race.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as setup_session:
            setup_session.add(User(telegram_id=123456789, username="winner"))
            await setup_session.commit()

        async with sessionmaker() as losing_session:
            original_execute = losing_session.execute
            stale_select_served = False

            async def execute_with_stale_first_lookup(statement, *args, **kwargs):
                nonlocal stale_select_served
                statement_text = str(statement.compile(compile_kwargs={"literal_binds": True}))
                if not stale_select_served and "FROM users" in statement_text:
                    stale_select_served = True

                    class EmptyResult:
                        @staticmethod
                        def scalar_one_or_none():
                            return None

                    return EmptyResult()

                return await original_execute(statement, *args, **kwargs)

            monkeypatch = pytest.MonkeyPatch()
            monkeypatch.setattr(losing_session, "execute", execute_with_stale_first_lookup)
            try:
                user = await get_or_create_user(
                    losing_session,
                    telegram_id=123456789,
                    username="resolved_username",
                )
                await losing_session.commit()
            finally:
                monkeypatch.undo()

        async with sessionmaker() as verification_session:
            users = (
                (await verification_session.execute(select(User).order_by(User.id))).scalars().all()
            )

        assert user.telegram_id == 123456789
        assert user.username == "resolved_username"
        assert len(users) == 1
        assert users[0].telegram_id == 123456789
        assert users[0].username == "resolved_username"
    finally:
        await engine.dispose()


async def test_list_due_reminder_jobs_returns_pending_and_stale_processing_jobs(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0, 0)
    stale_before = now - timedelta(minutes=5)

    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        name="Semion",
        phone="+79990000000",
        vehicle_plate="A001AA",
    )
    db_session.add(customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    db_session.add_all(
        [
            NotificationJob(
                car_wash_id=car_wash.id,
                booking_id=booking.id,
                kind="booking_reminder",
                run_at=now - timedelta(minutes=1),
                status="pending",
                attempts=0,
            ),
            NotificationJob(
                car_wash_id=car_wash.id,
                booking_id=booking.id,
                kind="booking_reminder",
                run_at=now - timedelta(minutes=10),
                status="processing",
                attempts=1,
                claimed_at=now - timedelta(minutes=10),
            ),
            NotificationJob(
                car_wash_id=car_wash.id,
                booking_id=booking.id,
                kind="booking_reminder",
                run_at=now + timedelta(minutes=10),
                status="pending",
                attempts=0,
            ),
            NotificationJob(
                car_wash_id=car_wash.id,
                booking_id=booking.id,
                kind="return_visit",
                run_at=now - timedelta(minutes=3),
                status="pending",
                attempts=0,
            ),
            NotificationJob(
                car_wash_id=car_wash.id,
                booking_id=booking.id,
                kind="booking_reminder",
                run_at=now - timedelta(minutes=3),
                status="sent",
                attempts=1,
            ),
            NotificationJob(
                car_wash_id=car_wash.id,
                booking_id=booking.id,
                kind="booking_reminder",
                run_at=now - timedelta(minutes=20),
                status="processing",
                attempts=1,
                claimed_at=now - timedelta(minutes=1),
            ),
        ]
    )
    await db_session.commit()

    jobs = await list_due_reminder_jobs(
        db_session,
        now=now,
        stale_before=stale_before,
        limit=10,
    )

    assert [job.status for job in jobs] == ["processing", "pending"]
    assert [job.attempts for job in jobs] == [1, 0]
    assert all(job.claimed_at != now - timedelta(minutes=1) for job in jobs)


async def test_claim_and_finalize_notification_job_updates_status_and_attempts(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0, 0)

    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        name="Semion",
        phone="+79990000000",
        vehicle_plate="A001AA",
    )
    db_session.add(customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    pending_job = NotificationJob(
        car_wash_id=car_wash.id,
        booking_id=booking.id,
        kind="booking_reminder",
        run_at=now,
        status="pending",
        attempts=0,
    )
    failed_job = NotificationJob(
        car_wash_id=car_wash.id,
        booking_id=booking.id,
        kind="booking_reminder",
        run_at=now,
        status="processing",
        attempts=1,
        claimed_at=now - timedelta(minutes=10),
    )
    skipped_job = NotificationJob(
        car_wash_id=car_wash.id,
        booking_id=booking.id,
        kind="booking_reminder",
        run_at=now,
        status="processing",
        attempts=2,
        claimed_at=now - timedelta(minutes=10),
    )
    db_session.add_all([pending_job, failed_job, skipped_job])
    await db_session.commit()

    claimed = await claim_notification_job(
        db_session,
        job_id=pending_job.id,
        expected_statuses=["pending"],
        claimed_at=now,
    )
    failed = await mark_notification_job_failed(db_session, job_id=failed_job.id, attempts=2)
    skipped = await mark_notification_job_skipped(db_session, job_id=skipped_job.id, attempts=2)
    sent = await mark_notification_job_sent(db_session, job_id=pending_job.id, attempts=1)
    await db_session.commit()

    jobs = (
        (await db_session.execute(select(NotificationJob).order_by(NotificationJob.id)))
        .scalars()
        .all()
    )

    assert claimed is True
    assert failed is True
    assert skipped is True
    assert sent is True
    assert [(job.status, job.attempts) for job in jobs] == [
        ("sent", 1),
        ("failed", 2),
        ("skipped", 2),
    ]


async def test_list_due_reminder_jobs_skips_recently_claimed_processing_jobs(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0, 0)
    stale_before = now - timedelta(minutes=5)

    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        name="Semion",
        phone="+79990000000",
        vehicle_plate="A001AA",
    )
    db_session.add(customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    db_session.add(
        NotificationJob(
            car_wash_id=car_wash.id,
            booking_id=booking.id,
            kind="booking_reminder",
            run_at=now - timedelta(minutes=30),
            status="processing",
            attempts=1,
            claimed_at=now - timedelta(minutes=1),
        )
    )
    await db_session.commit()

    jobs = await list_due_reminder_jobs(
        db_session,
        now=now,
        stale_before=stale_before,
        limit=10,
    )

    assert jobs == []


async def test_notification_job_finalization_refuses_jobs_outside_processing(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 5, 24, 12, 0, 0)

    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        name="Semion",
        phone="+79990000000",
        vehicle_plate="A001AA",
    )
    db_session.add(customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()
    pending_job = NotificationJob(
        car_wash_id=car_wash.id,
        booking_id=booking.id,
        kind="booking_reminder",
        run_at=now,
        status="pending",
        attempts=0,
    )
    sent_job = NotificationJob(
        car_wash_id=car_wash.id,
        booking_id=booking.id,
        kind="booking_reminder",
        run_at=now,
        status="sent",
        attempts=1,
    )
    db_session.add_all([pending_job, sent_job])
    await db_session.commit()

    skipped_pending = await mark_notification_job_skipped(
        db_session,
        job_id=pending_job.id,
        attempts=1,
    )
    failed_sent = await mark_notification_job_failed(
        db_session,
        job_id=sent_job.id,
        attempts=2,
    )
    await db_session.commit()

    jobs = (
        (await db_session.execute(select(NotificationJob).order_by(NotificationJob.id)))
        .scalars()
        .all()
    )

    assert skipped_pending is False
    assert failed_sent is False
    assert [(job.status, job.attempts) for job in jobs] == [
        ("pending", 0),
        ("sent", 1),
    ]
