from datetime import time
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Branch, CarWash, Service, User, WorkingHours
from app.db.repositories import (
    get_branch,
    get_or_create_user,
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


async def test_get_or_create_user_recovers_from_unique_conflict(tmp_path) -> None:
    database_path = tmp_path / "get-or-create-user-race.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as setup_session:
            setup_session.add(User(telegram_id=123456789, username="winner"))
            await setup_session.commit()

        async with sessionmaker() as losing_session:
            original_execute = losing_session.execute
            stale_select_served = False

            async def execute_with_stale_first_lookup(statement, *args, **kwargs):
                nonlocal stale_select_served
                statement_text = str(statement.compile(compile_kwargs={"literal_binds": True}))
                if not stale_select_served and "FROM users" in statement_text:
                    stale_select_served = True

                    class EmptyResult:
                        @staticmethod
                        def scalar_one_or_none():
                            return None

                    return EmptyResult()

                return await original_execute(statement, *args, **kwargs)

            monkeypatch = pytest.MonkeyPatch()
            monkeypatch.setattr(losing_session, "execute", execute_with_stale_first_lookup)
            try:
                user = await get_or_create_user(
                    losing_session,
                    telegram_id=123456789,
                    username="resolved_username",
                )
                await losing_session.commit()
            finally:
                monkeypatch.undo()

        async with sessionmaker() as verification_session:
            users = (
                (await verification_session.execute(select(User).order_by(User.id))).scalars().all()
            )

        assert user.telegram_id == 123456789
        assert user.username == "resolved_username"
        assert len(users) == 1
        assert users[0].telegram_id == 123456789
        assert users[0].username == "resolved_username"
    finally:
        await engine.dispose()
