from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BlockedSlot,
    Booking,
    BookingService as BookingServiceModel,
    Branch,
    CarWash,
    Customer,
    NotificationJob,
    Service,
    WorkingHours,
)
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


async def create_customer(
    session: AsyncSession,
    *,
    car_wash_id: int,
    name: str,
    phone: str,
    vehicle_plate: str,
) -> Customer:
    customer = Customer(
        car_wash_id=car_wash_id,
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
    session.add(BookingServiceModel(booking_id=booking_id, service_id=main_service_id, is_main=True))
    session.add_all(
        [
            BookingServiceModel(booking_id=booking_id, service_id=service_id, is_main=False)
            for service_id in addon_service_ids
        ]
    )
    await session.flush()


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
