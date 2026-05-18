from datetime import datetime
from decimal import Decimal

from app.bot.customer_booking.messages import (
    format_booking_summary,
    format_duration,
    format_money,
    service_line,
)
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
