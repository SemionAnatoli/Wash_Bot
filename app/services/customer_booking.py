from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.db.models import Booking, Service
from app.domain.errors import BookingSlotUnavailableError, CancellationTooLateError, DomainError
from app.domain.services import SelectedService, calculate_total_duration
from app.domain.slots import (
    BlockedInterval,
    BookingInterval,
    calculate_peak_occupancy,
    generate_available_slots,
)
from app.domain.statuses import BookingStatus, ensure_transition_allowed
from app.domain.validation import normalize_name, normalize_phone, normalize_vehicle_plate
from app.services.booking_service import BookingCapacity, ensure_booking_can_be_created


@dataclass(frozen=True, slots=True)
class ServiceOption:
    id: int
    title: str
    category: str
    price: Decimal
    duration_minutes: int
    is_addon: bool


@dataclass(frozen=True, slots=True)
class ServiceMenu:
    main_services: list[ServiceOption]
    addons: list[ServiceOption]


@dataclass(frozen=True, slots=True)
class ActiveCustomerBooking:
    booking_id: int
    status: str
    start_at: datetime
    end_at: datetime
    customer_name: str
    customer_phone: str
    vehicle_plate: str
    services: list[ServiceOption]


def _to_service_option(service: Service) -> ServiceOption:
    return ServiceOption(
        id=service.id,
        title=service.title,
        category=service.category,
        price=service.price,
        duration_minutes=service.duration_minutes,
        is_addon=service.is_addon,
    )


def _selected_service_from_model(service: Service) -> SelectedService:
    return SelectedService(
        id=service.id,
        title=service.title,
        duration_minutes=service.duration_minutes,
        is_addon=service.is_addon,
    )


class CustomerBookingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_service_menu(self, *, car_wash_id: int) -> ServiceMenu:
        main_services = await repositories.list_active_main_services(
            self._session,
            car_wash_id=car_wash_id,
        )
        addons = await repositories.list_active_addon_services(
            self._session,
            car_wash_id=car_wash_id,
        )
        return ServiceMenu(
            main_services=[_to_service_option(service) for service in main_services],
            addons=[_to_service_option(service) for service in addons],
        )

    async def get_available_slots(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        selected_service_ids: list[int],
        day: date,
    ) -> list[datetime]:
        branch = await repositories.get_branch(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
        )
        if branch is None:
            raise DomainError("Branch was not found.")

        hours = await repositories.get_working_hours_for_weekday(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            weekday=day.weekday(),
        )
        if hours is None:
            return []

        services = await repositories.list_services_by_ids(
            self._session,
            car_wash_id=car_wash_id,
            service_ids=selected_service_ids,
        )
        if len(services) != len(set(selected_service_ids)):
            raise DomainError("One or more services were not found.")

        main_services = [service for service in services if not service.is_addon]
        addons = [service for service in services if service.is_addon]
        if len(main_services) != 1:
            raise DomainError("Exactly one main service is required.")

        duration = calculate_total_duration(
            _selected_service_from_model(main_services[0]),
            [_selected_service_from_model(service) for service in addons],
        )
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day, time.max)
        booking_intervals = await repositories.list_overlapping_booking_intervals(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=day_start,
            end_at=day_end,
        )
        block_result = await self._session.execute(
            repositories.overlapping_blocks_query(
                car_wash_id=car_wash_id,
                branch_id=branch_id,
                start_at=day_start,
                end_at=day_end,
            )
        )
        blocks = list(block_result.scalars().all())

        return generate_available_slots(
            day=datetime.combine(day, time.min),
            work_start=hours.start_time,
            work_end=hours.end_time,
            duration=timedelta(minutes=duration),
            slot_step=timedelta(minutes=30),
            bay_count=branch.bay_count,
            bookings=[
                BookingInterval(start=start_at, end=end_at)
                for start_at, end_at in booking_intervals
            ],
            blocked=[
                BlockedInterval(start=blocked.start_at, end=blocked.end_at) for blocked in blocks
            ],
        )

    async def create_booking(
        self,
        *,
        car_wash_id: int,
        branch_id: int,
        selected_service_ids: list[int],
        start_at: datetime,
        customer_name: str,
        customer_phone: str,
        vehicle_plate: str,
        telegram_user_id: int | None = None,
        telegram_username: str | None = None,
    ) -> Booking:
        car_wash = await repositories.get_car_wash(self._session, car_wash_id=car_wash_id)
        if car_wash is None:
            raise DomainError("Car wash was not found.")

        branch = await repositories.get_branch(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
        )
        if branch is None:
            raise DomainError("Branch was not found.")

        services = await repositories.list_services_by_ids(
            self._session,
            car_wash_id=car_wash_id,
            service_ids=selected_service_ids,
        )
        if len(services) != len(set(selected_service_ids)):
            raise DomainError("One or more services were not found.")

        main_services = [service for service in services if not service.is_addon]
        addons = [service for service in services if service.is_addon]
        if len(main_services) != 1:
            raise DomainError("Exactly one main service is required.")

        duration = calculate_total_duration(
            _selected_service_from_model(main_services[0]),
            [_selected_service_from_model(service) for service in addons],
        )
        end_at = start_at + timedelta(minutes=duration)
        hours = await repositories.get_working_hours_for_weekday(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            weekday=start_at.weekday(),
        )
        if hours is None:
            raise BookingSlotUnavailableError("Cannot create booking outside working hours.")

        work_start_at = datetime.combine(start_at.date(), hours.start_time)
        work_end_at = datetime.combine(start_at.date(), hours.end_time)
        if start_at < work_start_at or end_at > work_end_at:
            raise BookingSlotUnavailableError("Cannot create booking outside working hours.")

        block_result = await self._session.execute(
            repositories.overlapping_blocks_query(
                car_wash_id=car_wash_id,
                branch_id=branch_id,
                start_at=start_at,
                end_at=end_at,
            )
        )
        overlapping_blocks = len(block_result.scalars().all())
        booking_intervals = await repositories.list_overlapping_booking_intervals(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            start_at=start_at,
            end_at=end_at,
        )
        peak_occupied_bays = calculate_peak_occupancy(
            start=start_at,
            end=end_at,
            bookings=[
                BookingInterval(start=interval_start, end=interval_end)
                for interval_start, interval_end in booking_intervals
            ],
        )
        ensure_booking_can_be_created(
            BookingCapacity(
                bay_count=branch.bay_count,
                peak_occupied_bays=peak_occupied_bays,
                overlapping_blocks=overlapping_blocks,
            )
        )

        user_id: int | None = None
        if telegram_user_id is not None:
            user = await repositories.get_or_create_user(
                self._session,
                telegram_id=telegram_user_id,
                username=telegram_username,
            )
            user_id = user.id

        customer = await repositories.create_customer(
            self._session,
            car_wash_id=car_wash_id,
            user_id=user_id,
            name=normalize_name(customer_name),
            phone=normalize_phone(customer_phone),
            vehicle_plate=normalize_vehicle_plate(vehicle_plate),
        )
        status = (
            BookingStatus.CONFIRMED
            if car_wash.confirmation_mode == "auto"
            else BookingStatus.PENDING
        )
        booking = await repositories.create_booking_record(
            self._session,
            car_wash_id=car_wash_id,
            branch_id=branch_id,
            customer_id=customer.id,
            start_at=start_at,
            end_at=end_at,
            status=status.value,
        )
        await repositories.add_booking_services(
            self._session,
            booking_id=booking.id,
            main_service_id=main_services[0].id,
            addon_service_ids=[service.id for service in addons],
        )
        await repositories.create_notification_job(
            self._session,
            car_wash_id=car_wash_id,
            booking_id=booking.id,
            kind="booking_reminder",
            run_at=start_at - timedelta(minutes=car_wash.reminder_before_minutes),
        )
        await self._session.commit()
        return booking

    async def get_active_booking(
        self,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
    ) -> ActiveCustomerBooking | None:
        current_time = now or datetime.now()
        booking_and_customer = await repositories.find_active_customer_booking(
            self._session,
            car_wash_id=car_wash_id,
            telegram_user_id=telegram_user_id,
            now=current_time,
        )
        if booking_and_customer is None:
            return None

        booking, customer = booking_and_customer
        booking_services = await repositories.list_booking_services(
            self._session,
            car_wash_id=car_wash_id,
            booking_id=booking.id,
        )
        return ActiveCustomerBooking(
            booking_id=booking.id,
            status=booking.status,
            start_at=booking.start_at,
            end_at=booking.end_at,
            customer_name=customer.name,
            customer_phone=customer.phone,
            vehicle_plate=customer.vehicle_plate,
            services=[_to_service_option(service) for _, service in booking_services],
        )

    async def cancel_active_booking(
        self,
        car_wash_id: int,
        telegram_user_id: int,
        now: datetime | None = None,
        cancellation_deadline_minutes: int = 60,
    ) -> bool:
        current_time = now or datetime.now()
        booking_and_customer = await repositories.find_active_customer_booking(
            self._session,
            car_wash_id=car_wash_id,
            telegram_user_id=telegram_user_id,
            now=current_time,
        )
        if booking_and_customer is None:
            return False

        booking, _ = booking_and_customer
        cancellation_deadline = booking.start_at - timedelta(minutes=cancellation_deadline_minutes)
        if current_time > cancellation_deadline:
            raise CancellationTooLateError("Booking can no longer be cancelled.")

        ensure_transition_allowed(
            BookingStatus(booking.status),
            BookingStatus.CANCELLED_BY_CUSTOMER,
        )
        cancelled = await repositories.update_active_booking_status(
            self._session,
            booking_id=booking.id,
            status=BookingStatus.CANCELLED_BY_CUSTOMER.value,
        )
        if not cancelled:
            return False

        await self._session.commit()
        return True
