from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Booking, Branch, CarWash, Service, WorkingHours
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
