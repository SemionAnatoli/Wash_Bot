from datetime import time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, CarWash, Service, WorkingHours
from app.db.repositories import (
    get_branch,
    get_working_hours_for_weekday,
    list_active_addon_services,
    list_active_main_services,
)


async def test_service_repositories_split_main_services_and_addons(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    db_session.add_all(
        [
            Service(
                car_wash_id=car_wash.id,
                title="Body wash",
                category="wash",
                price=Decimal("500"),
                duration_minutes=30,
                is_addon=False,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Wax",
                category="addon",
                price=Decimal("200"),
                duration_minutes=15,
                is_addon=True,
                is_active=True,
            ),
            Service(
                car_wash_id=car_wash.id,
                title="Old package",
                category="wash",
                price=Decimal("1000"),
                duration_minutes=60,
                is_addon=False,
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    main_services = await list_active_main_services(db_session, car_wash_id=car_wash.id)
    addons = await list_active_addon_services(db_session, car_wash_id=car_wash.id)

    assert [service.title for service in main_services] == ["Body wash"]
    assert [service.title for service in addons] == ["Wax"]


async def test_branch_and_working_hours_repositories_return_config(
    db_session: AsyncSession,
) -> None:
    car_wash = CarWash(name="Wash")
    db_session.add(car_wash)
    await db_session.flush()
    branch = Branch(
        car_wash_id=car_wash.id,
        title="Main",
        address="Street",
        bay_count=2,
    )
    db_session.add(branch)
    await db_session.flush()
    db_session.add(
        WorkingHours(
            car_wash_id=car_wash.id,
            branch_id=branch.id,
            weekday=0,
            start_time=time(9),
            end_time=time(18),
        )
    )
    await db_session.commit()

    loaded_branch = await get_branch(db_session, car_wash_id=car_wash.id, branch_id=branch.id)
    hours = await get_working_hours_for_weekday(
        db_session,
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        weekday=0,
    )

    assert loaded_branch is not None
    assert loaded_branch.bay_count == 2
    assert hours is not None
    assert hours.start_time == time(9)
    assert hours.end_time == time(18)
