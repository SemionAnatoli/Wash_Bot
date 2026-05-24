from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, BookingService, Branch, CarWash, Customer, Service
from app.domain.statuses import BookingStatus
from app.services.admin_booking import AdminBookingActionStatus, AdminBookingService


@dataclass(frozen=True, slots=True)
class BookingSeed:
    car_wash: CarWash
    branch: Branch
    customer: Customer
    main_service: Service
    addon_service: Service


async def seed_booking_context(db_session: AsyncSession) -> BookingSeed:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()

    branch = Branch(
        car_wash_id=car_wash.id,
        title="Main",
        address="Street",
        bay_count=1,
    )
    db_session.add(branch)
    await db_session.flush()

    customer = Customer(
        car_wash_id=car_wash.id,
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
    addon_service = Service(
        car_wash_id=car_wash.id,
        title="Wax",
        category="addon",
        price=Decimal("250"),
        duration_minutes=15,
        is_addon=True,
        is_active=True,
    )
    db_session.add_all([main_service, addon_service])
    await db_session.flush()
    return BookingSeed(
        car_wash=car_wash,
        branch=branch,
        customer=customer,
        main_service=main_service,
        addon_service=addon_service,
    )


async def seed_booking(
    db_session: AsyncSession,
    *,
    context: BookingSeed | None = None,
    status: str = BookingStatus.PENDING.value,
    start_at: datetime = datetime(2026, 5, 24, 10),
    branch: Branch | None = None,
) -> tuple[BookingSeed, Booking]:
    context = context or await seed_booking_context(db_session)
    booking_branch = branch or context.branch
    booking = Booking(
        car_wash_id=context.car_wash.id,
        branch_id=booking_branch.id,
        customer_id=context.customer.id,
        start_at=start_at,
        end_at=start_at + timedelta(minutes=75),
        status=status,
    )
    db_session.add(booking)
    await db_session.flush()
    db_session.add_all(
        [
            BookingService(
                booking_id=booking.id,
                service_id=context.main_service.id,
                is_main=True,
            ),
            BookingService(
                booking_id=booking.id,
                service_id=context.addon_service.id,
                is_main=False,
            ),
        ]
    )
    await db_session.commit()
    return context, booking


def test_admin_access_uses_configured_ids() -> None:
    service = AdminBookingService(db_session=None, admin_telegram_ids=(1001, 1002))

    assert service.is_admin(1001) is True
    assert service.is_admin(2001) is False


async def test_list_today_bookings_returns_active_bookings_for_branch(
    db_session: AsyncSession,
) -> None:
    context, pending = await seed_booking(db_session, status=BookingStatus.PENDING.value)
    _, confirmed = await seed_booking(
        db_session,
        context=context,
        status=BookingStatus.CONFIRMED.value,
        start_at=datetime(2026, 5, 24, 11),
    )
    other_branch = Branch(
        car_wash_id=context.car_wash.id,
        title="Second",
        address="Other street",
        bay_count=1,
    )
    db_session.add(other_branch)
    await db_session.flush()
    await seed_booking(
        db_session,
        context=context,
        status=BookingStatus.PENDING.value,
        start_at=datetime(2026, 5, 24, 12),
        branch=other_branch,
    )
    await seed_booking(
        db_session,
        context=context,
        status=BookingStatus.PENDING.value,
        start_at=datetime(2026, 5, 25, 10),
    )

    bookings = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).list_today_bookings(
        car_wash_id=context.car_wash.id,
        branch_id=context.branch.id,
        today=date(2026, 5, 24),
    )

    assert [booking.booking_id for booking in bookings] == [pending.id, confirmed.id]
    assert bookings[0].customer_name == "Ivan"
    assert [service.title for service in bookings[0].services] == ["Standard", "Wax"]
    assert bookings[0].total_price == Decimal("1150")
    assert bookings[0].total_duration_minutes == 75


async def test_list_today_bookings_ignores_terminal_statuses(
    db_session: AsyncSession,
) -> None:
    context = await seed_booking_context(db_session)
    for status in (
        BookingStatus.CANCELLED_BY_CUSTOMER.value,
        BookingStatus.CANCELLED_BY_ADMIN.value,
        BookingStatus.COMPLETED.value,
        BookingStatus.NO_SHOW.value,
    ):
        await seed_booking(db_session, context=context, status=status)

    bookings = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).list_today_bookings(
        car_wash_id=context.car_wash.id,
        branch_id=context.branch.id,
        today=date(2026, 5, 24),
    )

    assert bookings == []


async def test_get_booking_details_rejects_cross_tenant_customer_link(
    db_session: AsyncSession,
) -> None:
    context = await seed_booking_context(db_session)
    other_car_wash = CarWash(name="Other wash")
    db_session.add(other_car_wash)
    await db_session.flush()
    other_customer = Customer(
        car_wash_id=other_car_wash.id,
        name="Petr",
        phone="+79130000000",
        vehicle_plate="B456CD154",
    )
    db_session.add(other_customer)
    await db_session.flush()
    booking = Booking(
        car_wash_id=context.car_wash.id,
        branch_id=context.branch.id,
        customer_id=other_customer.id,
        start_at=datetime(2026, 5, 24, 10),
        end_at=datetime(2026, 5, 24, 11),
        status=BookingStatus.PENDING.value,
    )
    db_session.add(booking)
    await db_session.commit()

    details = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).get_booking_details(car_wash_id=context.car_wash.id, booking_id=booking.id)

    assert details is None


async def test_confirm_pending_booking_changes_status(db_session: AsyncSession) -> None:
    context, booking = await seed_booking(db_session, status=BookingStatus.PENDING.value)

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).confirm_booking(car_wash_id=context.car_wash.id, booking_id=booking.id)

    persisted_status = (
        await db_session.execute(select(Booking.status).where(Booking.id == booking.id))
    ).scalar_one()
    assert result.status == AdminBookingActionStatus.CHANGED
    assert result.booking is not None
    assert result.booking.status == BookingStatus.CONFIRMED.value
    assert persisted_status == BookingStatus.CONFIRMED.value


async def test_confirm_non_pending_booking_returns_current_status(
    db_session: AsyncSession,
) -> None:
    context, booking = await seed_booking(db_session, status=BookingStatus.CONFIRMED.value)

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).confirm_booking(car_wash_id=context.car_wash.id, booking_id=booking.id)

    assert result.status == AdminBookingActionStatus.STALE
    assert result.booking is not None
    assert result.booking.status == BookingStatus.CONFIRMED.value


async def test_cancel_active_booking_changes_status(db_session: AsyncSession) -> None:
    context, booking = await seed_booking(db_session, status=BookingStatus.CONFIRMED.value)

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).cancel_booking(car_wash_id=context.car_wash.id, booking_id=booking.id)

    persisted_status = (
        await db_session.execute(select(Booking.status).where(Booking.id == booking.id))
    ).scalar_one()
    assert result.status == AdminBookingActionStatus.CHANGED
    assert result.booking is not None
    assert result.booking.status == BookingStatus.CANCELLED_BY_ADMIN.value
    assert persisted_status == BookingStatus.CANCELLED_BY_ADMIN.value


async def test_cancel_terminal_booking_returns_current_status(
    db_session: AsyncSession,
) -> None:
    context, booking = await seed_booking(db_session, status=BookingStatus.COMPLETED.value)

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).cancel_booking(car_wash_id=context.car_wash.id, booking_id=booking.id)

    assert result.status == AdminBookingActionStatus.STALE
    assert result.booking is not None
    assert result.booking.status == BookingStatus.COMPLETED.value


async def test_admin_action_rejects_wrong_car_wash(db_session: AsyncSession) -> None:
    _, booking = await seed_booking(db_session, status=BookingStatus.PENDING.value)

    result = await AdminBookingService(
        db_session,
        admin_telegram_ids=(1001,),
    ).confirm_booking(car_wash_id=999, booking_id=booking.id)

    assert result.status == AdminBookingActionStatus.NOT_FOUND
    assert result.booking is None
