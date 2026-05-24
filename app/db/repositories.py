from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BlockedSlot,
    Booking,
    Branch,
    CarWash,
    Customer,
    NotificationJob,
    Service,
    User,
    WorkingHours,
)
from app.db.models import BookingService as BookingServiceModel
from app.domain.statuses import BookingStatus

ACTIVE_CAPACITY_STATUSES = [BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]


def overlapping_bookings_query(
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> Select[tuple[Booking]]:
    return select(Booking).where(
        Booking.car_wash_id == car_wash_id,
        Booking.branch_id == branch_id,
        Booking.status.in_(ACTIVE_CAPACITY_STATUSES),
        Booking.start_at < end_at,
        Booking.end_at > start_at,
    )


def overlapping_blocks_query(
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> Select[tuple[BlockedSlot]]:
    return select(BlockedSlot).where(
        BlockedSlot.car_wash_id == car_wash_id,
        BlockedSlot.branch_id == branch_id,
        BlockedSlot.start_at < end_at,
        BlockedSlot.end_at > start_at,
    )


def count_overlapping_bookings_query(
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> Select[tuple[int]]:
    """Count overlapping rows only; capacity decisions need interval peak occupancy."""
    return (
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.car_wash_id == car_wash_id,
            Booking.branch_id == branch_id,
            Booking.status.in_(ACTIVE_CAPACITY_STATUSES),
            Booking.start_at < end_at,
            Booking.end_at > start_at,
        )
    )


def overlapping_booking_intervals_query(
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> Select[tuple[datetime, datetime]]:
    return select(Booking.start_at, Booking.end_at).where(
        Booking.car_wash_id == car_wash_id,
        Booking.branch_id == branch_id,
        Booking.status.in_(ACTIVE_CAPACITY_STATUSES),
        Booking.start_at < end_at,
        Booking.end_at > start_at,
    )


async def count_overlapping_bookings(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> int:
    result = await session.execute(
        count_overlapping_bookings_query(
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=start_at,
            end_at=end_at,
        )
    )
    return result.scalar_one()


async def list_overlapping_booking_intervals(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> list[tuple[datetime, datetime]]:
    result = await session.execute(
        overlapping_booking_intervals_query(
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=start_at,
            end_at=end_at,
        )
    )
    return [(interval_start, interval_end) for interval_start, interval_end in result.all()]


async def list_active_main_services(session: AsyncSession, *, car_wash_id: int) -> list[Service]:
    result = await session.execute(
        select(Service)
        .where(
            Service.car_wash_id == car_wash_id,
            Service.is_active.is_(True),
            Service.is_addon.is_(False),
        )
        .order_by(Service.id)
    )
    return list(result.scalars().all())


async def list_active_addon_services(session: AsyncSession, *, car_wash_id: int) -> list[Service]:
    result = await session.execute(
        select(Service)
        .where(
            Service.car_wash_id == car_wash_id,
            Service.is_active.is_(True),
            Service.is_addon.is_(True),
        )
        .order_by(Service.id)
    )
    return list(result.scalars().all())


async def get_branch(session: AsyncSession, *, car_wash_id: int, branch_id: int) -> Branch | None:
    result = await session.execute(
        select(Branch).where(Branch.car_wash_id == car_wash_id, Branch.id == branch_id)
    )
    return result.scalar_one_or_none()


async def get_working_hours_for_weekday(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    weekday: int,
) -> WorkingHours | None:
    result = await session.execute(
        select(WorkingHours).where(
            WorkingHours.car_wash_id == car_wash_id,
            WorkingHours.branch_id == branch_id,
            WorkingHours.weekday == weekday,
        )
    )
    return result.scalar_one_or_none()


async def list_services_by_ids(
    session: AsyncSession,
    *,
    car_wash_id: int,
    service_ids: list[int],
) -> list[Service]:
    if not service_ids:
        return []

    result = await session.execute(
        select(Service)
        .where(
            Service.car_wash_id == car_wash_id,
            Service.id.in_(set(service_ids)),
            Service.is_active.is_(True),
        )
        .order_by(Service.id)
    )
    return list(result.scalars().all())


async def get_car_wash(session: AsyncSession, *, car_wash_id: int) -> CarWash | None:
    result = await session.execute(select(CarWash).where(CarWash.id == car_wash_id))
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        try:
            async with session.begin_nested():
                session.add(user)
                await session.flush()
        except IntegrityError:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user is None:
                raise
        else:
            return user

    if username is not None and user.username != username:
        user.username = username
        await session.flush()

    return user


async def create_customer(
    session: AsyncSession,
    *,
    car_wash_id: int,
    user_id: int | None = None,
    name: str,
    phone: str,
    vehicle_plate: str,
) -> Customer:
    customer = Customer(
        car_wash_id=car_wash_id,
        user_id=user_id,
        name=name,
        phone=phone,
        vehicle_plate=vehicle_plate,
    )
    session.add(customer)
    await session.flush()
    return customer


async def create_booking_record(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    customer_id: int,
    start_at: datetime,
    end_at: datetime,
    status: str,
) -> Booking:
    booking = Booking(
        car_wash_id=car_wash_id,
        branch_id=branch_id,
        customer_id=customer_id,
        start_at=start_at,
        end_at=end_at,
        status=status,
    )
    session.add(booking)
    await session.flush()
    return booking


async def add_booking_services(
    session: AsyncSession,
    *,
    booking_id: int,
    main_service_id: int,
    addon_service_ids: list[int],
) -> None:
    session.add(
        BookingServiceModel(
            booking_id=booking_id,
            service_id=main_service_id,
            is_main=True,
        )
    )
    session.add_all(
        [
            BookingServiceModel(booking_id=booking_id, service_id=service_id, is_main=False)
            for service_id in addon_service_ids
        ]
    )
    await session.flush()


async def find_active_customer_booking(
    session: AsyncSession,
    *,
    car_wash_id: int,
    telegram_user_id: int,
    now: datetime,
) -> tuple[Booking, Customer] | None:
    result = await session.execute(
        select(Booking, Customer)
        .join(Customer, Customer.id == Booking.customer_id)
        .join(User, User.id == Customer.user_id)
        .where(
            Booking.car_wash_id == car_wash_id,
            Customer.car_wash_id == car_wash_id,
            User.telegram_id == telegram_user_id,
            Booking.status.in_(ACTIVE_CAPACITY_STATUSES),
            Booking.start_at > now,
        )
        .order_by(Booking.start_at, Booking.id)
        .limit(1)
    )
    row = result.one_or_none()
    if row is None:
        return None

    return (row[0], row[1])


async def list_booking_services(
    session: AsyncSession,
    *,
    car_wash_id: int,
    booking_id: int,
) -> list[tuple[BookingServiceModel, Service]]:
    result = await session.execute(
        select(BookingServiceModel, Service)
        .join(Service, Service.id == BookingServiceModel.service_id)
        .where(
            BookingServiceModel.booking_id == booking_id,
            Service.car_wash_id == car_wash_id,
        )
        .order_by(BookingServiceModel.is_main.desc(), Service.id)
    )
    return [(booking_service, service) for booking_service, service in result.all()]


async def list_bookings_for_day(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    day_start: datetime,
    day_end: datetime,
) -> list[Booking]:
    result = await session.execute(
        select(Booking)
        .where(
            Booking.car_wash_id == car_wash_id,
            Booking.branch_id == branch_id,
            Booking.status.in_(ACTIVE_CAPACITY_STATUSES),
            Booking.start_at >= day_start,
            Booking.start_at < day_end,
        )
        .order_by(Booking.start_at, Booking.id)
    )
    return list(result.scalars().all())


async def get_booking_with_customer(
    session: AsyncSession,
    *,
    car_wash_id: int,
    booking_id: int,
) -> tuple[Booking, Customer] | None:
    result = await session.execute(
        select(Booking, Customer)
        .join(Customer, Customer.id == Booking.customer_id)
        .where(
            Booking.car_wash_id == car_wash_id,
            Booking.id == booking_id,
            Customer.car_wash_id == car_wash_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    return row[0], row[1]


async def update_booking_status_if_current(
    session: AsyncSession,
    *,
    booking_id: int,
    current_statuses: list[str],
    new_status: str,
) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(Booking)
            .where(
                Booking.id == booking_id,
                Booking.status.in_(current_statuses),
            )
            .values(status=new_status)
            .execution_options(synchronize_session="fetch")
        ),
    )
    return result.rowcount == 1


async def update_active_booking_status(
    session: AsyncSession,
    *,
    booking_id: int,
    status: str,
) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(Booking)
            .where(
                Booking.id == booking_id,
                Booking.status.in_(ACTIVE_CAPACITY_STATUSES),
            )
            .values(status=status)
            .execution_options(synchronize_session=False)
        ),
    )
    return result.rowcount == 1


async def create_notification_job(
    session: AsyncSession,
    *,
    car_wash_id: int,
    booking_id: int,
    kind: str,
    run_at: datetime,
) -> NotificationJob:
    job = NotificationJob(
        car_wash_id=car_wash_id,
        booking_id=booking_id,
        kind=kind,
        run_at=run_at,
        status="pending",
        attempts=0,
    )
    session.add(job)
    await session.flush()
    return job
