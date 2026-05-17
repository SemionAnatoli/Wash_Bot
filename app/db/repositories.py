from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BlockedSlot, Booking
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


async def count_overlapping_bookings(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
    start_at: datetime,
    end_at: datetime,
) -> int:
    result = await session.execute(
        overlapping_bookings_query(
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=start_at,
            end_at=end_at,
        )
    )
    return len(result.scalars().all())
