from dataclasses import dataclass
from datetime import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Branch, CarWash, Service, WorkingHours


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    car_wash_id: int
    branch_id: int
    main_service_count: int
    addon_service_count: int
    working_hours_count: int


DEMO_MAIN_SERVICES = (
    ("Стандартная мойка", "wash", Decimal("900.00"), 60),
    ("Комплекс", "wash", Decimal("1500.00"), 90),
)

DEMO_ADDON_SERVICES = (
    ("Воск", "addon", Decimal("250.00"), 15),
    ("Чернение шин", "addon", Decimal("200.00"), 10),
    ("Уборка салона", "addon", Decimal("700.00"), 30),
)


async def seed_demo_data(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
) -> DemoSeedResult:
    car_wash = await _ensure_car_wash(session, car_wash_id=car_wash_id)
    branch = await _ensure_branch(
        session,
        car_wash_id=car_wash.id,
        branch_id=branch_id,
    )
    await _ensure_working_hours(session, car_wash_id=car_wash.id, branch_id=branch.id)
    await _ensure_services(session, car_wash_id=car_wash.id)
    await session.commit()

    return DemoSeedResult(
        car_wash_id=car_wash.id,
        branch_id=branch.id,
        main_service_count=len(DEMO_MAIN_SERVICES),
        addon_service_count=len(DEMO_ADDON_SERVICES),
        working_hours_count=7,
    )


async def _ensure_car_wash(session: AsyncSession, *, car_wash_id: int) -> CarWash:
    car_wash = await session.get(CarWash, car_wash_id)
    if car_wash is None:
        car_wash = CarWash(id=car_wash_id, name="Demo Wash")
        session.add(car_wash)
        await session.flush()

    car_wash.name = "Demo Wash"
    car_wash.confirmation_mode = "manual"
    car_wash.reminder_before_minutes = 60
    return car_wash


async def _ensure_branch(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
) -> Branch:
    branch = await session.get(Branch, branch_id)
    if branch is None or branch.car_wash_id != car_wash_id:
        result = await session.execute(
            select(Branch).where(Branch.car_wash_id == car_wash_id, Branch.title == "Main")
        )
        branch = result.scalar_one_or_none()

    if branch is None:
        branch = Branch(
            id=branch_id,
            car_wash_id=car_wash_id,
            title="Main",
            address="Demo street",
            bay_count=1,
        )
        session.add(branch)
        await session.flush()

    branch.title = "Main"
    branch.address = "Demo street"
    branch.bay_count = 1
    return branch


async def _ensure_working_hours(
    session: AsyncSession,
    *,
    car_wash_id: int,
    branch_id: int,
) -> None:
    for weekday in range(7):
        result = await session.execute(
            select(WorkingHours).where(
                WorkingHours.car_wash_id == car_wash_id,
                WorkingHours.branch_id == branch_id,
                WorkingHours.weekday == weekday,
            )
        )
        working_hours = result.scalar_one_or_none()
        if working_hours is None:
            working_hours = WorkingHours(
                car_wash_id=car_wash_id,
                branch_id=branch_id,
                weekday=weekday,
                start_time=time(10),
                end_time=time(20),
            )
            session.add(working_hours)
        else:
            working_hours.start_time = time(10)
            working_hours.end_time = time(20)


async def _ensure_services(session: AsyncSession, *, car_wash_id: int) -> None:
    for title, category, price, duration_minutes in DEMO_MAIN_SERVICES:
        await _ensure_service(
            session,
            car_wash_id=car_wash_id,
            title=title,
            category=category,
            price=price,
            duration_minutes=duration_minutes,
            is_addon=False,
        )
    for title, category, price, duration_minutes in DEMO_ADDON_SERVICES:
        await _ensure_service(
            session,
            car_wash_id=car_wash_id,
            title=title,
            category=category,
            price=price,
            duration_minutes=duration_minutes,
            is_addon=True,
        )


async def _ensure_service(
    session: AsyncSession,
    *,
    car_wash_id: int,
    title: str,
    category: str,
    price: Decimal,
    duration_minutes: int,
    is_addon: bool,
) -> Service:
    result = await session.execute(
        select(Service).where(Service.car_wash_id == car_wash_id, Service.title == title)
    )
    service = result.scalar_one_or_none()
    if service is None:
        service = Service(
            car_wash_id=car_wash_id,
            title=title,
            category=category,
            price=price,
            duration_minutes=duration_minutes,
            is_addon=is_addon,
            is_active=True,
        )
        session.add(service)
    else:
        service.category = category
        service.price = price
        service.duration_minutes = duration_minutes
        service.is_addon = is_addon
        service.is_active = True
    return service
