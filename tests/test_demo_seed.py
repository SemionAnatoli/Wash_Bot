from datetime import time
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, CarWash, Service, WorkingHours
from app.demo_seed import seed_demo_data


async def count_rows(db_session: AsyncSession, model: type[Any]) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_demo_data_creates_local_demo_setup(db_session: AsyncSession) -> None:
    result = await seed_demo_data(db_session, car_wash_id=1, branch_id=1)

    car_wash = await db_session.get(CarWash, result.car_wash_id)
    branch = await db_session.get(Branch, result.branch_id)
    services = (
        (await db_session.execute(select(Service).order_by(Service.is_addon, Service.title)))
        .scalars()
        .all()
    )
    hours = (
        (await db_session.execute(select(WorkingHours).order_by(WorkingHours.weekday)))
        .scalars()
        .all()
    )

    assert car_wash is not None
    assert car_wash.name == "Demo Wash"
    assert car_wash.confirmation_mode == "manual"
    assert car_wash.reminder_before_minutes == 60
    assert branch is not None
    assert branch.car_wash_id == car_wash.id
    assert branch.title == "Main"
    assert branch.address == "Demo street"
    assert branch.bay_count == 1
    assert result.main_service_count == 2
    assert result.addon_service_count == 3
    assert [
        (service.title, service.price, service.duration_minutes, service.is_addon)
        for service in services
    ] == [
        ("Комплекс", Decimal("1500.00"), 90, False),
        ("Стандартная мойка", Decimal("900.00"), 60, False),
        ("Воск", Decimal("250.00"), 15, True),
        ("Уборка салона", Decimal("700.00"), 30, True),
        ("Чернение шин", Decimal("200.00"), 10, True),
    ]
    assert len(hours) == 7
    assert {working_hours.weekday for working_hours in hours} == set(range(7))
    assert all(working_hours.start_time == time(10) for working_hours in hours)
    assert all(working_hours.end_time == time(20) for working_hours in hours)


async def test_seed_demo_data_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_demo_data(db_session, car_wash_id=1, branch_id=1)
    second = await seed_demo_data(db_session, car_wash_id=1, branch_id=1)

    assert first == second
    assert await count_rows(db_session, CarWash) == 1
    assert await count_rows(db_session, Branch) == 1
    assert await count_rows(db_session, Service) == 5
    assert await count_rows(db_session, WorkingHours) == 7
