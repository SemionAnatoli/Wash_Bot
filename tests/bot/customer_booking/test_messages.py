from datetime import datetime
from decimal import Decimal

from app.bot.customer_booking.messages import (
    ACTIVE_BOOKING_ALREADY_EXISTS_TEXT,
    ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT,
    ACTIVE_BOOKING_CANCELLED_TEXT,
    ACTIVE_BOOKING_EMPTY_TEXT,
    format_active_booking_summary,
    format_booking_summary,
    format_duration,
    format_money,
    service_line,
)
from app.services.customer_booking import ActiveCustomerBooking, ServiceOption


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


def test_format_money_and_duration() -> None:
    assert format_money(Decimal("900")) == "900 руб."
    assert format_money(Decimal("900.50")) == "900.50 руб."
    assert format_duration(0) == "0 мин"
    assert format_duration(30) == "30 мин"
    assert format_duration(60) == "1 ч"
    assert format_duration(90) == "1 ч 30 мин"


def test_service_line_contains_title_price_and_duration() -> None:
    text = service_line(option(1, "Стандарт", "900", 60))

    assert text == "Стандарт — 900 руб., 1 ч"


def test_active_booking_text_constants_are_stable() -> None:
    assert ACTIVE_BOOKING_EMPTY_TEXT == "У вас нет активной записи."
    assert ACTIVE_BOOKING_CANCELLED_TEXT == "Запись отменена."
    assert (
        ACTIVE_BOOKING_CANCEL_TOO_LATE_TEXT
        == "Отменить запись уже нельзя. Свяжитесь с администратором."
    )


def test_active_booking_already_exists_text_is_stable() -> None:
    assert (
        ACTIVE_BOOKING_ALREADY_EXISTS_TEXT
        == "У вас уже есть активная запись. Откройте «Моя запись», "
        "чтобы посмотреть или отменить её."
    )


def test_booking_summary_escapes_html_dynamic_fields() -> None:
    text = format_booking_summary(
        main_service=option(1, "Foam <Basic> & Shine", "900", 60),
        addons=[option(2, "Wax > Ceramic & Seal", "250", 15, is_addon=True)],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Ann <Bob> & Co",
        customer_phone="+7 <913> & 123",
        vehicle_plate="A<123>&BC",
    )

    assert "Foam &lt;Basic&gt; &amp; Shine" in text
    assert "Wax &gt; Ceramic &amp; Seal" in text
    assert "Ann &lt;Bob&gt; &amp; Co" in text
    assert "+7 &lt;913&gt; &amp; 123" in text
    assert "A&lt;123&gt;&amp;BC" in text
    assert "Foam <Basic> & Shine" not in text
    assert "Ann <Bob> & Co" not in text


def test_format_booking_summary_contains_customer_choice() -> None:
    text = format_booking_summary(
        main_service=option(1, "Стандарт", "900", 60),
        addons=[option(2, "Воск", "250", 15, is_addon=True)],
        start_at=datetime(2026, 5, 18, 10),
        customer_name="Иван",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
    )

    assert "Стандарт" in text
    assert "Воск" in text
    assert "18.05.2026 10:00" in text
    assert "Иван" in text
    assert "+79131234567" in text
    assert "A123BC154" in text
    assert "1 ч 15 мин" in text
    assert "1150 руб." in text


def test_format_active_booking_summary_contains_booking_details() -> None:
    booking = ActiveCustomerBooking(
        booking_id=42,
        status="confirmed",
        start_at=datetime(2026, 5, 18, 10),
        end_at=datetime(2026, 5, 18, 11, 15),
        customer_name="Иван",
        customer_phone="+79131234567",
        vehicle_plate="A123BC154",
        services=[
            option(1, "Стандарт", "900", 60),
            option(2, "Воск", "250", 15, is_addon=True),
        ],
    )

    text = format_active_booking_summary(booking)

    assert "Ваша запись" in text
    assert "18.05.2026 10:00" in text
    assert "Подтверждена" in text
    assert "A123BC154" in text
    assert "Стандарт — 900 руб., 1 ч" in text
    assert "Воск — 250 руб., 15 мин" in text
    assert "1 ч 15 мин" in text
    assert "1150 руб." in text
    assert "Иван" in text
    assert "+79131234567" in text


def test_format_active_booking_summary_escapes_html_dynamic_fields() -> None:
    booking = ActiveCustomerBooking(
        booking_id=42,
        status="pending",
        start_at=datetime(2026, 5, 18, 10),
        end_at=datetime(2026, 5, 18, 11),
        customer_name="Ann <Bob> & Co",
        customer_phone="+7 <913> & 123",
        vehicle_plate="A<123>&BC",
        services=[
            option(1, "Foam <Basic> & Shine", "900", 60),
        ],
    )

    text = format_active_booking_summary(booking)

    assert "Ожидает подтверждения" in text
    assert "Foam &lt;Basic&gt; &amp; Shine" in text
    assert "Ann &lt;Bob&gt; &amp; Co" in text
    assert "+7 &lt;913&gt; &amp; 123" in text
    assert "A&lt;123&gt;&amp;BC" in text
    assert "Foam <Basic> & Shine" not in text
    assert "Ann <Bob> & Co" not in text
