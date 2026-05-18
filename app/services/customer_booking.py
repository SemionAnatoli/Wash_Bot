from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories
from app.db.models import Service


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
