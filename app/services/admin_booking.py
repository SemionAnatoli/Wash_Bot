from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.db.models import Service
from app.domain.statuses import BookingStatus, ensure_transition_allowed
from app.services.customer_booking import ServiceOption


@dataclass(frozen=True, slots=True)
class AdminBookingDetails:
    booking_id: int
    status: str
    start_at: datetime
    end_at: datetime
    customer_name: str
    customer_phone: str
    vehicle_plate: str
    services: list[ServiceOption]

    @property
    def total_price(self) -> Decimal:
        return sum((service.price for service in self.services), Decimal("0"))

    @property
    def total_duration_minutes(self) -> int:
        return sum(service.duration_minutes for service in self.services)


class AdminBookingActionStatus(StrEnum):
    CHANGED = "changed"
    STALE = "stale"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class AdminBookingActionResult:
    status: AdminBookingActionStatus
    booking: AdminBookingDetails | None


def _to_service_option(service: Service) -> ServiceOption:
    return ServiceOption(
        id=service.id,
        title=service.title,
        category=service.category,
        price=service.price,
        duration_minutes=service.duration_minutes,
        is_addon=service.is_addon,
    )


class AdminBookingService:
    def __init__(
        self,
        db_session: AsyncSession | None,
        *,
        admin_telegram_ids: tuple[int, ...],
    ) -> None:
        self._session = db_session
        self._admin_telegram_ids = set(admin_telegram_ids)

    def is_admin(self, telegram_user_id: int) -> bool:
        return telegram_user_id in self._admin_telegram_ids

    async def list_today_bookings(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        today: date,
    ) -> list[AdminBookingDetails]:
        session = self._require_session()
        day_start = datetime.combine(today, time.min)
        day_end = day_start + timedelta(days=1)
        bookings = await repositories.list_bookings_for_day(
            session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            day_start=day_start,
            day_end=day_end,
        )

        details: list[AdminBookingDetails] = []
        for booking in bookings:
            booking_details = await self.get_booking_details(
                car_wash_id=car_wash_id,
                booking_id=booking.id,
            )
            if booking_details is not None:
                details.append(booking_details)
        return details

    async def get_booking_details(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingDetails | None:
        session = self._require_session()
        row = await repositories.get_booking_with_customer(
            session,
            car_wash_id=car_wash_id,
            booking_id=booking_id,
        )
        if row is None:
            return None

        booking, customer = row
        service_rows = await repositories.list_booking_services(
            session,
            car_wash_id=car_wash_id,
            booking_id=booking.id,
        )
        return AdminBookingDetails(
            booking_id=booking.id,
            status=booking.status,
            start_at=booking.start_at,
            end_at=booking.end_at,
            customer_name=customer.name,
            customer_phone=customer.phone,
            vehicle_plate=customer.vehicle_plate,
            services=[_to_service_option(service) for _, service in service_rows],
        )

    async def confirm_booking(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingActionResult:
        booking = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
        if booking is None:
            return AdminBookingActionResult(AdminBookingActionStatus.NOT_FOUND, None)
        if booking.status != BookingStatus.PENDING.value:
            return AdminBookingActionResult(AdminBookingActionStatus.STALE, booking)

        ensure_transition_allowed(BookingStatus(booking.status), BookingStatus.CONFIRMED)
        changed = await repositories.update_booking_status_if_current(
            self._require_session(),
            booking_id=booking_id,
            current_statuses=[BookingStatus.PENDING.value],
            new_status=BookingStatus.CONFIRMED.value,
        )
        return await self._action_result_after_update(
            changed=changed,
            car_wash_id=car_wash_id,
            booking_id=booking_id,
        )

    async def cancel_booking(
        self,
        *,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingActionResult:
        booking = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
        if booking is None:
            return AdminBookingActionResult(AdminBookingActionStatus.NOT_FOUND, None)
        if booking.status not in {
            BookingStatus.PENDING.value,
            BookingStatus.CONFIRMED.value,
        }:
            return AdminBookingActionResult(AdminBookingActionStatus.STALE, booking)

        ensure_transition_allowed(BookingStatus(booking.status), BookingStatus.CANCELLED_BY_ADMIN)
        changed = await repositories.update_booking_status_if_current(
            self._require_session(),
            booking_id=booking_id,
            current_statuses=[BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value],
            new_status=BookingStatus.CANCELLED_BY_ADMIN.value,
        )
        return await self._action_result_after_update(
            changed=changed,
            car_wash_id=car_wash_id,
            booking_id=booking_id,
        )

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Database session is required.")
        return self._session

    async def _action_result_after_update(
        self,
        *,
        changed: bool,
        car_wash_id: int,
        booking_id: int,
    ) -> AdminBookingActionResult:
        if changed:
            await self._require_session().commit()
            current = await self.get_booking_details(
                car_wash_id=car_wash_id,
                booking_id=booking_id,
            )
            return AdminBookingActionResult(AdminBookingActionStatus.CHANGED, current)

        current = await self.get_booking_details(car_wash_id=car_wash_id, booking_id=booking_id)
        if current is None:
            return AdminBookingActionResult(AdminBookingActionStatus.NOT_FOUND, None)
        return AdminBookingActionResult(AdminBookingActionStatus.STALE, current)
