from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import repositories
from app.db.base import Base
from app.db.models import (
    Booking,
    BookingService,
    Branch,
    CarWash,
    Customer,
    NotificationJob,
    Service,
    User,
    WorkingHours,
)
from app.domain.errors import (
    ActiveBookingAlreadyExistsError,
    BookingSlotUnavailableError,
    CancellationTooLateError,
    DomainError,
)
from app.domain.statuses import BookingStatus
from app.services.admin_booking import AdminBookingActionStatus, AdminBookingService
from app.services.customer_booking import CustomerBookingService
from app.worker.reminders import process_due_reminder_jobs


class FakeReminderGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.calls.append((telegram_id, text))


async def test_get_service_menu_returns_main_services_and_addons(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    db_session.add_all(
        [
            Service(
                car_wash_id=car_wash.id,
                title="Standard",
                category="wash",
                price=Decimal("900"),
                duration_minutes=60,
                is_addon=False,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Wax",
                category="addon",
                price=Decimal("250"),
                duration_minutes=15,
                is_addon=True,
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    menu = await CustomerBookingService(db_session).get_service_menu(car_wash_id=car_wash.id)

    assert [service.title for service in menu.main_services] == ["Standard"]
    assert [service.title for service in menu.addons] == ["Wax"]
    assert menu.main_services[0].price == Decimal("900")


async def test_get_available_slots_uses_services_working_hours_and_capacity(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    db_session.add(branch)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=120,
        is_addon=False,
        is_active=True,
    )
    db_session.add(main_service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    db_session.add_all(
        [
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 10),
                end_at=datetime(2026, 5, 18, 11),
                status="confirmed",
            ),
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 11),
                end_at=datetime(2026, 5, 18, 12),
                status="confirmed",
            ),
        ]
    )
    await db_session.commit()

    slots = await CustomerBookingService(db_session).get_available_slots(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[main_service.id],
        day=date(2026, 5, 18),
    )

    assert slots == [datetime(2026, 5, 18, 10)]


async def test_create_booking_persists_customer_booking_services_and_reminder(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(main_service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[main_service.id],
        start_at=datetime(2026, 5, 18, 10),
        customer_name=" Ivan ",
        customer_phone="8 (913) 123-45-67",
        vehicle_plate="a123bc154",
    )

    customers = (await db_session.execute(select(Customer))).scalars().all()
    booking_services = (await db_session.execute(select(BookingService))).scalars().all()
    jobs = (await db_session.execute(select(NotificationJob))).scalars().all()

    assert booking.status == "confirmed"
    assert booking.end_at == datetime(2026, 5, 18, 11)
    assert customers[0].name == "Ivan"
    assert customers[0].phone == "+79131234567"
    assert customers[0].vehicle_plate == "A123BC154"
    assert len(booking_services) == 1
    assert jobs[0].kind == "booking_reminder"
    assert jobs[0].run_at == datetime(2026, 5, 18, 9)


async def test_create_booking_links_customer_to_telegram_user(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(main_service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[main_service.id],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        telegram_user_id=123456789,
        telegram_username="ivan_detailing",
    )

    verification_sessionmaker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
    )
    async with verification_sessionmaker() as verification_session:
        customer = (await verification_session.execute(select(Customer))).scalar_one()
        user = (await verification_session.execute(select(User))).scalar_one()

    assert user.telegram_id == 123456789
    assert user.username == "ivan_detailing"
    assert customer.user_id == user.id


async def test_manual_booking_confirmation_allows_worker_to_send_reminder(
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 6, 1, 9)
    start_at = datetime(2026, 6, 1, 10)
    car_wash = CarWash(name="Wash", confirmation_mode="manual", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(main_service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=start_at.weekday(),
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[main_service.id],
        start_at=start_at,
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        telegram_user_id=123456789,
        telegram_username="ivan_detailing",
    )
    assert booking.status == BookingStatus.PENDING.value

    confirm_result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).confirm_booking(car_wash_id=car_wash.id, booking_id=booking.id)
    sessionmaker = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    gateway = FakeReminderGateway()

    worker_result = await process_due_reminder_jobs(sessionmaker, gateway, now=now)

    async with sessionmaker() as verification_session:
        persisted_booking_status = (
            await verification_session.execute(
                select(Booking.status).where(Booking.id == booking.id)
            )
        ).scalar_one()
        persisted_job = (
            await verification_session.execute(
                select(NotificationJob).where(NotificationJob.booking_id == booking.id)
            )
        ).scalar_one()

    assert confirm_result.status == AdminBookingActionStatus.CHANGED
    assert confirm_result.booking is not None
    assert confirm_result.booking.status == BookingStatus.CONFIRMED.value
    assert worker_result.sent == 1
    assert worker_result.skipped == 0
    assert worker_result.failed == 0
    assert gateway.calls == [(123456789, gateway.calls[0][1])]
    assert "01.06.2026" in gateway.calls[0][1]
    assert "10:00" in gateway.calls[0][1]
    assert persisted_booking_status == BookingStatus.CONFIRMED.value
    assert persisted_job.status == "sent"
    assert persisted_job.attempts == 1


async def test_create_booking_reuses_existing_telegram_user_and_updates_username(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    existing_user = User(telegram_id=123456789, username="old_username")
    db_session.add_all([car_wash, existing_user])
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(main_service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[main_service.id],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        telegram_user_id=existing_user.telegram_id,
        telegram_username="new_username",
    )

    verification_sessionmaker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
    )
    async with verification_sessionmaker() as verification_session:
        users = (await verification_session.execute(select(User).order_by(User.id))).scalars().all()
        customer = (await verification_session.execute(select(Customer))).scalar_one()

    assert len(users) == 1
    assert users[0].id == existing_user.id
    assert users[0].username == "new_username"
    assert customer.user_id == existing_user.id


async def test_create_booking_rejects_second_future_active_booking_for_same_telegram_user(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(15),
        )
    )
    await db_session.commit()

    booking_service = CustomerBookingService(db_session)
    first_booking = await booking_service.create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[service.id],
        start_at=datetime(2026, 6, 1, 10),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        telegram_user_id=123456789,
        telegram_username="ivan_detailing",
    )

    with pytest.raises(ActiveBookingAlreadyExistsError):
        await booking_service.create_booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            selected_service_ids=[service.id],
            start_at=datetime(2026, 6, 1, 12),
            customer_name="Ivan",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
            telegram_user_id=123456789,
            telegram_username="ivan_detailing",
        )

    customers = (await db_session.execute(select(Customer).order_by(Customer.id))).scalars().all()
    bookings = (await db_session.execute(select(Booking).order_by(Booking.id))).scalars().all()
    active_booking = await booking_service.get_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=123456789,
        now=datetime(2026, 6, 1, 9),
    )

    assert len(customers) == 1
    assert len(bookings) == 1
    assert bookings[0].id == first_booking.id
    assert active_booking is not None
    assert active_booking.booking_id == first_booking.id


async def test_create_booking_rejects_slot_when_capacity_is_full(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    db_session.add(
        Booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            customer_id=1,
            start_at=datetime(2026, 5, 18, 10),
            end_at=datetime(2026, 5, 18, 11),
            status="confirmed",
        )
    )
    await db_session.commit()

    with pytest.raises(DomainError):
        await CustomerBookingService(db_session).create_booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            selected_service_ids=[service.id],
            start_at=datetime(2026, 5, 18, 10),
            customer_name="Ivan",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
        )


async def test_create_booking_rejects_slot_overrunning_close_time(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    with pytest.raises(BookingSlotUnavailableError):
        await CustomerBookingService(db_session).create_booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            selected_service_ids=[service.id],
            start_at=datetime(2026, 5, 18, 11, 30),
            customer_name="Ivan",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
        )

    assert (await db_session.execute(select(Customer))).scalars().all() == []
    assert (await db_session.execute(select(Booking))).scalars().all() == []


async def test_create_booking_rejects_slot_without_working_hours(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.commit()

    with pytest.raises(BookingSlotUnavailableError):
        await CustomerBookingService(db_session).create_booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            selected_service_ids=[service.id],
            start_at=datetime(2026, 5, 18, 10),
            customer_name="Ivan",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
        )

    assert (await db_session.execute(select(Customer))).scalars().all() == []
    assert (await db_session.execute(select(Booking))).scalars().all() == []


async def test_create_booking_rejects_slot_before_open_time(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=1)
    db_session.add(branch)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    await db_session.commit()

    with pytest.raises(BookingSlotUnavailableError):
        await CustomerBookingService(db_session).create_booking(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            selected_service_ids=[service.id],
            start_at=datetime(2026, 5, 18, 9, 30),
            customer_name="Ivan",
            customer_phone="+79131234567",
            vehicle_plate="A123BC154",
        )

    assert (await db_session.execute(select(Customer))).scalars().all() == []
    assert (await db_session.execute(select(Booking))).scalars().all() == []


async def test_create_booking_allows_sequential_existing_bookings_with_free_peak_capacity(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash", confirmation_mode="auto", reminder_before_minutes=60)
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    db_session.add(branch)
    await db_session.flush()
    service = Service(
        car_wash_id=car_wash.id,
        title="Long package",
        category="wash",
        price=Decimal("1500"),
        duration_minutes=120,
        is_addon=False,
        is_active=True,
    )
    db_session.add(service)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(10),
            end_time=time(12),
        )
    )
    db_session.add_all(
        [
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 10),
                end_at=datetime(2026, 5, 18, 11),
                status="confirmed",
            ),
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=1,
                start_at=datetime(2026, 5, 18, 11),
                end_at=datetime(2026, 5, 18, 12),
                status="confirmed",
            ),
        ]
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).create_booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        selected_service_ids=[service.id],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Ivan",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
    )

    assert booking.start_at == datetime(2026, 5, 18, 10)
    assert booking.end_at == datetime(2026, 5, 18, 12)


async def test_get_active_booking_returns_earliest_future_active_booking_with_services(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    user = User(telegram_id=123456789, username="washer")
    db_session.add_all([branch, user])
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        user_id=user.id,
        name="Ivan",
        phone="+79131234567",
        vehicle_plate="A123BC154",
    )
    db_session.add(customer)
    await db_session.flush()
    main_service = Service(
        car_wash_id=car_wash.id,
        title="Standard",
        category="wash",
        price=Decimal("900"),
        duration_minutes=60,
        is_addon=False,
        is_active=True,
    )
    addon = Service(
        car_wash_id=car_wash.id,
        title="Wax",
        category="addon",
        price=Decimal("250"),
        duration_minutes=15,
        is_addon=True,
        is_active=True,
    )
    db_session.add_all([main_service, addon])
    await db_session.flush()
    later_booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=datetime(2026, 5, 19, 13),
        end_at=datetime(2026, 5, 19, 14),
        status=BookingStatus.CONFIRMED.value,
    )
    earliest_booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=datetime(2026, 5, 19, 11),
        end_at=datetime(2026, 5, 19, 12, 15),
        status=BookingStatus.PENDING.value,
    )
    db_session.add_all([later_booking, earliest_booking])
    await db_session.flush()
    db_session.add_all(
        [
            BookingService(
                booking_id=earliest_booking.id,
                service_id=addon.id,
                is_main=False,
            ),
            BookingService(
                booking_id=earliest_booking.id,
                service_id=main_service.id,
                is_main=True,
            ),
        ]
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).get_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=user.telegram_id,
        now=datetime(2026, 5, 19, 10),
    )

    assert booking is not None
    assert booking.booking_id == earliest_booking.id
    assert booking.status == BookingStatus.PENDING.value
    assert booking.start_at == datetime(2026, 5, 19, 11)
    assert booking.end_at == datetime(2026, 5, 19, 12, 15)
    assert booking.customer_name == "Ivan"
    assert booking.customer_phone == "+79131234567"
    assert booking.vehicle_plate == "A123BC154"
    assert [service.title for service in booking.services] == ["Standard", "Wax"]


async def test_get_active_booking_ignores_past_and_inactive_bookings(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    user = User(telegram_id=123456789, username="washer")
    other_user = User(telegram_id=987654321, username="other")
    db_session.add_all([branch, user, other_user])
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        user_id=user.id,
        name="Ivan",
        phone="+79131234567",
        vehicle_plate="A123BC154",
    )
    other_customer = Customer(
        car_wash_id=car_wash.id,
        user_id=other_user.id,
        name="Petr",
        phone="+79130000000",
        vehicle_plate="B456CD154",
    )
    db_session.add_all([customer, other_customer])
    await db_session.flush()
    db_session.add_all(
        [
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=customer.id,
                start_at=datetime(2026, 5, 19, 9),
                end_at=datetime(2026, 5, 19, 10),
                status=BookingStatus.CONFIRMED.value,
            ),
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=customer.id,
                start_at=datetime(2026, 5, 19, 12),
                end_at=datetime(2026, 5, 19, 13),
                status=BookingStatus.CANCELLED_BY_CUSTOMER.value,
            ),
            Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=other_customer.id,
                start_at=datetime(2026, 5, 19, 12),
                end_at=datetime(2026, 5, 19, 13),
                status=BookingStatus.CONFIRMED.value,
            ),
        ]
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).get_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=user.telegram_id,
        now=datetime(2026, 5, 19, 10),
    )

    assert booking is None


async def test_get_active_booking_returns_none_for_cross_tenant_customer_link(
    db_session: AsyncSession,
) -> None:
    car_wash_a = CarWash(name="Wash A")
    car_wash_b = CarWash(name="Wash B")
    user = User(telegram_id=123456789, username="washer")
    db_session.add_all([car_wash_a, car_wash_b, user])
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash_a.id, title="Main", address="Street", bay_count=2)
    db_session.add(branch)
    await db_session.flush()
    mismatched_customer = Customer(
        car_wash_id=car_wash_b.id,
        user_id=user.id,
        name="Ivan",
        phone="+79131234567",
        vehicle_plate="A123BC154",
    )
    db_session.add(mismatched_customer)
    await db_session.flush()
    db_session.add(
        Booking(
            car_wash_id=car_wash_a.id,
            branch_id=branch.id,
            customer_id=mismatched_customer.id,
            start_at=datetime(2026, 5, 19, 12),
            end_at=datetime(2026, 5, 19, 13),
            status=BookingStatus.CONFIRMED.value,
        )
    )
    await db_session.commit()

    booking = await CustomerBookingService(db_session).get_active_booking(
        car_wash_id=car_wash_a.id,
        telegram_user_id=user.telegram_id,
        now=datetime(2026, 5, 19, 10),
    )

    assert booking is None


async def test_cancel_active_booking_updates_status_when_allowed(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    user = User(telegram_id=123456789, username="washer")
    db_session.add_all([branch, user])
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        user_id=user.id,
        name="Ivan",
        phone="+79131234567",
        vehicle_plate="A123BC154",
    )
    db_session.add(customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=datetime(2026, 5, 19, 12),
        end_at=datetime(2026, 5, 19, 13),
        status=BookingStatus.CONFIRMED.value,
    )
    db_session.add(booking)
    await db_session.commit()

    cancelled = await CustomerBookingService(db_session).cancel_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=user.telegram_id,
        now=datetime(2026, 5, 19, 10),
    )

    refreshed_status = (
        await db_session.execute(select(Booking.status).where(Booking.id == booking.id))
    ).scalar_one()
    assert cancelled is True
    assert refreshed_status == BookingStatus.CANCELLED_BY_CUSTOMER.value


async def test_cancel_active_booking_allows_exactly_60_minutes_before_start(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    user = User(telegram_id=123456789, username="washer")
    db_session.add_all([branch, user])
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        user_id=user.id,
        name="Ivan",
        phone="+79131234567",
        vehicle_plate="A123BC154",
    )
    db_session.add(customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=datetime(2026, 5, 19, 12),
        end_at=datetime(2026, 5, 19, 13),
        status=BookingStatus.PENDING.value,
    )
    db_session.add(booking)
    await db_session.commit()

    cancelled = await CustomerBookingService(db_session).cancel_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=user.telegram_id,
        now=datetime(2026, 5, 19, 11),
    )

    refreshed_status = (
        await db_session.execute(select(Booking.status).where(Booking.id == booking.id))
    ).scalar_one()
    assert cancelled is True
    assert refreshed_status == BookingStatus.CANCELLED_BY_CUSTOMER.value


async def test_cancel_active_booking_rejects_less_than_60_minutes_before_start(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(car_wash_id=car_wash.id, title="Main", address="Street", bay_count=2)
    user = User(telegram_id=123456789, username="washer")
    db_session.add_all([branch, user])
    await db_session.flush()
    customer = Customer(
        car_wash_id=car_wash.id,
        user_id=user.id,
        name="Ivan",
        phone="+79131234567",
        vehicle_plate="A123BC154",
    )
    db_session.add(customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        customer_id=customer.id,
        start_at=datetime(2026, 5, 19, 12),
        end_at=datetime(2026, 5, 19, 13),
        status=BookingStatus.CONFIRMED.value,
    )
    db_session.add(booking)
    await db_session.commit()

    with pytest.raises(CancellationTooLateError):
        await CustomerBookingService(db_session).cancel_active_booking(
            car_wash_id=car_wash.id,
            telegram_user_id=user.telegram_id,
            now=datetime(2026, 5, 19, 11, 1),
        )

    refreshed_status = (
        await db_session.execute(select(Booking.status).where(Booking.id == booking.id))
    ).scalar_one()
    assert refreshed_status == BookingStatus.CONFIRMED.value


async def test_cancel_active_booking_returns_false_without_active_booking(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    user = User(telegram_id=123456789, username="washer")
    db_session.add_all([car_wash, user])
    await db_session.commit()

    cancelled = await CustomerBookingService(db_session).cancel_active_booking(
        car_wash_id=car_wash.id,
        telegram_user_id=user.telegram_id,
        now=datetime(2026, 5, 19, 10),
    )

    assert cancelled is False


async def test_cancel_active_booking_returns_false_when_booking_completed_concurrently(
    tmp_path,
) -> None:
    database_path = tmp_path / "customer-booking-race.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as setup_session:
            car_wash = CarWash(name="Wash")
            setup_session.add(car_wash)
            await setup_session.flush()
            branch = Branch(
                car_wash_id=car_wash.id,
                title="Main",
                address="Street",
                bay_count=2,
            )
            user = User(telegram_id=123456789, username="washer")
            setup_session.add_all([branch, user])
            await setup_session.flush()
            customer = Customer(
                car_wash_id=car_wash.id,
                user_id=user.id,
                name="Ivan",
                phone="+79131234567",
                vehicle_plate="A123BC154",
            )
            setup_session.add(customer)
            await setup_session.flush()
            booking = Booking(
                car_wash_id=car_wash.id,
                branch_id=branch.id,
                customer_id=customer.id,
                start_at=datetime(2026, 5, 19, 12),
                end_at=datetime(2026, 5, 19, 13),
                status=BookingStatus.CONFIRMED.value,
            )
            setup_session.add(booking)
            await setup_session.commit()
            car_wash_id = car_wash.id
            telegram_user_id = user.telegram_id
            booking_id = booking.id

        original_find = repositories.find_active_customer_booking

        async def concurrent_find_active_customer_booking(
            session: AsyncSession,
            *,
            car_wash_id: int,
            telegram_user_id: int,
            now: datetime,
        ) -> tuple[Booking, Customer] | None:
            booking_and_customer = await original_find(
                session,
                car_wash_id=car_wash_id,
                telegram_user_id=telegram_user_id,
                now=now,
            )
            assert booking_and_customer is not None

            async with sessionmaker() as concurrent_session:
                concurrent_booking = await concurrent_session.get(Booking, booking_id)
                assert concurrent_booking is not None
                concurrent_booking.status = BookingStatus.COMPLETED.value
                await concurrent_session.commit()

            return booking_and_customer

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            repositories,
            "find_active_customer_booking",
            concurrent_find_active_customer_booking,
        )
        try:
            async with sessionmaker() as cancellation_session:
                cancelled = await CustomerBookingService(
                    cancellation_session
                ).cancel_active_booking(
                    car_wash_id=car_wash_id,
                    telegram_user_id=telegram_user_id,
                    now=datetime(2026, 5, 19, 10),
                )
        finally:
            monkeypatch.undo()

        async with sessionmaker() as verification_session:
            persisted_status = (
                await verification_session.execute(
                    select(Booking.status).where(Booking.id == booking_id)
                )
            ).scalar_one()

        assert cancelled is False
        assert persisted_status == BookingStatus.COMPLETED.value
    finally:
        await engine.dispose()
