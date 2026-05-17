from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CarWash


async def test_async_db_session_fixture_persists_rows(db_session: AsyncSession) -> None:
    db_session.add(CarWash(name="Test wash"))
    await db_session.commit()

    result = await db_session.execute(select(CarWash.name))

    assert result.scalar_one() == "Test wash"
