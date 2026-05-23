from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.domain.errors import BookingSlotUnavailableError, CancellationTooLateError, DomainError
from app.domain.statuses import BookingStatus
from app.services.customer_booking import CustomerBookingService


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

    customer = (await db_session.execute(select(Customer))).scalar_one()
    user = (await db_session.execute(select(User))).scalar_one()

    assert user.telegram_id == 123456789
    assert user.username == "ivan_detailing"
    assert customer.user_id == user.id


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

    refreshed = await db_session.get(Booking, booking.id)
    assert cancelled is True
    assert refreshed is not None
    assert refreshed.status == BookingStatus.CANCELLED_BY_CUSTOMER.value


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

    refreshed = await db_session.get(Booking, booking.id)
    assert cancelled is True
    assert refreshed is not None
    assert refreshed.status == BookingStatus.CANCELLED_BY_CUSTOMER.value


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

    refreshed = await db_session.get(Booking, booking.id)
    assert refreshed is not None
    assert refreshed.status == BookingStatus.CONFIRMED.value


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
