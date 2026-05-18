from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CarWash, Service
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
