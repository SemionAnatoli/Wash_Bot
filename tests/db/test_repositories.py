from datetime import datetime
from typing import Any

import pytest
from sqlalchemy.sql import Select

from app.db.repositories import (
    count_overlapping_bookings,
    count_overlapping_bookings_query,
    overlapping_bookings_query,
)
from app.domain.statuses import BookingStatus

REQUESTED_START = datetime(2026, 5, 18, 10, 0)
REQUESTED_END = datetime(2026, 5, 18, 11, 0)


def test_overlapping_bookings_query_filters_only_capacity_occupying_statuses() -> None:
    statement = overlapping_bookings_query(
        car_wash_id=1,
        branch_id=2,
        start_at=REQUESTED_START,
        end_at=REQUESTED_END,
    )

    assert statement.compile().params["status_1"] == [
        BookingStatus.PENDING.value,
        BookingStatus.CONFIRMED.value,
    ]
    assert BookingStatus.CANCELLED_BY_CUSTOMER.value not in statement.compile().params["status_1"]
    assert BookingStatus.CANCELLED_BY_ADMIN.value not in statement.compile().params["status_1"]
    assert BookingStatus.COMPLETED.value not in statement.compile().params["status_1"]
    assert BookingStatus.NO_SHOW.value not in statement.compile().params["status_1"]


def test_overlapping_bookings_query_uses_half_open_overlap_bounds() -> None:
    statement = overlapping_bookings_query(
        car_wash_id=1,
        branch_id=2,
        start_at=REQUESTED_START,
        end_at=REQUESTED_END,
    )
    compiled = statement.compile()

    assert "bookings.start_at <" in str(compiled)
    assert "bookings.end_at >" in str(compiled)
    assert compiled.params["start_at_1"] == REQUESTED_END
    assert compiled.params["end_at_1"] == REQUESTED_START


def test_count_overlapping_bookings_query_counts_rows_with_same_overlap_filters() -> None:
    statement = count_overlapping_bookings_query(
        car_wash_id=1,
        branch_id=2,
        start_at=REQUESTED_START,
        end_at=REQUESTED_END,
    )
    compiled = statement.compile()
    sql = str(compiled).lower()

    assert "select count(" in sql
    assert "from bookings" in sql
    assert "bookings.status in" in sql
    assert "bookings.start_at <" in sql
    assert "bookings.end_at >" in sql
    assert compiled.params["status_1"] == [
        BookingStatus.PENDING.value,
        BookingStatus.CONFIRMED.value,
    ]
    assert compiled.params["start_at_1"] == REQUESTED_END
    assert compiled.params["end_at_1"] == REQUESTED_START


@pytest.mark.asyncio
async def test_count_overlapping_bookings_executes_count_query_with_scalar_one() -> None:
    class Result:
        def scalar_one(self) -> int:
            return 3

        def scalars(self) -> Any:
            raise AssertionError("count_overlapping_bookings should not materialize rows")

    class Session:
        statement: Select[tuple[int]] | None = None

        async def execute(self, statement: Select[tuple[int]]) -> Result:
            self.statement = statement
            return Result()

    session = Session()

    count = await count_overlapping_bookings(
        session,  # type: ignore[arg-type]
        car_wash_id=1,
        branch_id=2,
        start_at=REQUESTED_START,
        end_at=REQUESTED_END,
    )

    assert count == 3
    assert session.statement is not None
    assert "select count(" in str(session.statement.compile()).lower()
