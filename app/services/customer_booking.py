from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.db.models import Service
from app.domain.errors import DomainError
from app.domain.services import SelectedService, calculate_total_duration
from app.domain.slots import (
    BlockedInterval,
    BookingInterval,
    generate_available_slots,
)


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
                BlockedInterval(start=blocked.start_at, end=blocked.end_at)
                for blocked in blocks
            ],
        )
