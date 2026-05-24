import pytest

from app.bot.admin_bookings.callbacks import (
    ADMIN_TODAY_CALLBACK,
    build_admin_cancel_callback,
    build_admin_confirm_callback,
    parse_admin_booking_id,
)


def test_admin_callback_builders_are_stable() -> None:
    assert ADMIN_TODAY_CALLBACK == "admin:today"
    assert build_admin_confirm_callback(15) == "admin:confirm:15"
    assert build_admin_cancel_callback(15) == "admin:cancel:15"


def test_admin_callback_parser_returns_booking_id() -> None:
    assert parse_admin_booking_id("admin:confirm:15", prefix="admin:confirm") == 15
    assert parse_admin_booking_id("admin:cancel:42", prefix="admin:cancel") == 42


def test_admin_callback_parser_rejects_unexpected_prefix() -> None:
    with pytest.raises(ValueError, match="Unexpected admin callback prefix"):
        parse_admin_booking_id("book:confirm:15", prefix="admin:confirm")


def test_admin_callback_parser_rejects_non_integer_id() -> None:
    with pytest.raises(ValueError):
        parse_admin_booking_id("admin:confirm:not-an-id", prefix="admin:confirm")
