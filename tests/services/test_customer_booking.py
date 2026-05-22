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
    WorkingHours,
)
from app.domain.errors import BookingSlotUnavailableError, DomainError
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
