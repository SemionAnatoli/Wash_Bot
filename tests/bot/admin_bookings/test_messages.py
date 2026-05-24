from datetime import datetime
from decimal import Decimal

from app.bot.admin_bookings.messages import (
    ADMIN_ACCESS_DENIED_TEXT,
    ADMIN_BOOKING_CANCELLED_TEXT,
    ADMIN_BOOKING_CONFIRMED_TEXT,
    ADMIN_BOOKING_NOT_FOUND_TEXT,
    ADMIN_TODAY_EMPTY_TEXT,
    format_admin_booking_details,
    format_admin_today_bookings,
)
from app.services.admin_booking import AdminBookingDetails
from app.services.customer_booking import ServiceOption


def option(
    service_id: int,
    title: str,
    price: str,
    duration_minutes: int,
    *,
    is_addon: bool = False,
) -> ServiceOption:
    return ServiceOption(
        id=service_id,
        title=title,
        category="addon" if is_addon else "wash",
        price=Decimal(price),
        duration_minutes=duration_minutes,
        is_addon=is_addon,
    )


def booking_details(
    *,
    booking_id: int = 42,
    status: str = "pending",
    customer_name: str = "Иван",
    customer_phone: str = "+79131234567",
    vehicle_plate: str = "A123BC154",
) -> AdminBookingDetails:
    return AdminBookingDetails(
        booking_id=booking_id,
        status=status,
        start_at=datetime(2026, 5, 24, 10),
        end_at=datetime(2026, 5, 24, 11, 15),
        customer_name=customer_name,
        customer_phone=customer_phone,
        vehicle_plate=vehicle_plate,
        services=[
            option(1, "Стандарт", "900", 60),
            option(2, "Воск", "250", 15, is_addon=True),
        ],
    )


def test_admin_text_constants_are_stable() -> None:
    assert ADMIN_ACCESS_DENIED_TEXT == "Недостаточно прав."
    assert ADMIN_TODAY_EMPTY_TEXT == "Сегодня записей нет."
    assert ADMIN_BOOKING_CONFIRMED_TEXT == "Запись подтверждена."
    assert ADMIN_BOOKING_CANCELLED_TEXT == "Запись отменена."
    assert ADMIN_BOOKING_NOT_FOUND_TEXT == "Запись не найдена."


def test_format_admin_booking_details_contains_booking_summary() -> None:
    text = format_admin_booking_details(booking_details())

    assert "Новая запись" in text
    assert "24.05.2026 10:00" in text
    assert "Ожидает подтверждения" in text
    assert "Иван" in text
    assert "+79131234567" in text
    assert "A123BC154" in text
    assert "Стандарт" in text
    assert "Воск" in text
    assert "1 ч 15 мин" in text
    assert "1150 руб." in text


def test_format_admin_booking_details_escapes_dynamic_fields() -> None:
    text = format_admin_booking_details(
        AdminBookingDetails(
            booking_id=42,
            status="confirmed",
            start_at=datetime(2026, 5, 24, 10),
            end_at=datetime(2026, 5, 24, 11),
            customer_name="Ann <Bob> & Co",
            customer_phone="+7 <913> & 123",
            vehicle_plate="A<123>&BC",
            services=[option(1, "Foam <Basic> & Shine", "900", 60)],
        )
    )

    assert "Foam &lt;Basic&gt; &amp; Shine" in text
    assert "Ann &lt;Bob&gt; &amp; Co" in text
    assert "+7 &lt;913&gt; &amp; 123" in text
    assert "A&lt;123&gt;&amp;BC" in text
    assert "Foam <Basic> & Shine" not in text
    assert "Ann <Bob> & Co" not in text


def test_format_admin_today_bookings_lists_bookings_in_order() -> None:
    text = format_admin_today_bookings(
        [
            booking_details(booking_id=10, status="pending"),
            booking_details(booking_id=11, status="confirmed", customer_name="Петр"),
        ]
    )

    assert "Сегодняшние записи" in text
    assert "10:00" in text
    assert "#10" in text
    assert "#11" in text
    assert "Иван" in text
    assert "Петр" in text
    assert "Ожидает подтверждения" in text
    assert "Подтверждена" in text


def test_format_admin_today_bookings_returns_empty_state() -> None:
    assert format_admin_today_bookings([]) == ADMIN_TODAY_EMPTY_TEXT
