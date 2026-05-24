from html import escape

from app.bot.customer_booking.messages import format_duration, format_money, service_line
from app.services.admin_booking import AdminBookingDetails

ADMIN_ACCESS_DENIED_TEXT = "Недостаточно прав."
ADMIN_TODAY_EMPTY_TEXT = "Сегодня записей нет."
ADMIN_BOOKING_CONFIRMED_TEXT = "Запись подтверждена."
ADMIN_BOOKING_CANCELLED_TEXT = "Запись отменена."
ADMIN_BOOKING_NOT_FOUND_TEXT = "Запись не найдена."

_STATUS_LABELS = {
    "pending": "Ожидает подтверждения",
    "confirmed": "Подтверждена",
    "cancelled_by_customer": "Отменена клиентом",
    "cancelled_by_admin": "Отменена администратором",
    "completed": "Завершена",
    "no_show": "Клиент не приехал",
}


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, escape(status))


def format_admin_booking_details(
    booking: AdminBookingDetails,
    *,
    title: str = "Новая запись",
) -> str:
    customer_name = escape(booking.customer_name)
    customer_phone = escape(booking.customer_phone)
    vehicle_plate = escape(booking.vehicle_plate)
    service_lines = "\n".join(f"- {service_line(service)}" for service in booking.services)
    if not service_lines:
        service_lines = "Услуги не указаны"

    return (
        f"{escape(title)}\n"
        f"Запись: #{booking.booking_id}\n"
        f"Дата и время: {booking.start_at:%d.%m.%Y %H:%M}\n"
        f"Статус: {status_label(booking.status)}\n"
        f"Клиент: {customer_name}\n"
        f"Телефон: {customer_phone}\n"
        f"Автомобиль: {vehicle_plate}\n"
        f"Услуги:\n{service_lines}\n"
        f"Длительность: {format_duration(booking.total_duration_minutes)}\n"
        f"Итого: {format_money(booking.total_price)}"
    )


def format_admin_today_bookings(bookings: list[AdminBookingDetails]) -> str:
    if not bookings:
        return ADMIN_TODAY_EMPTY_TEXT

    lines = ["Сегодняшние записи:"]
    for booking in bookings:
        services = ", ".join(escape(service.title) for service in booking.services)
        if not services:
            services = "услуги не указаны"
        lines.append(
            f"{booking.start_at:%H:%M} #{booking.booking_id} - "
            f"{escape(booking.customer_name)}, {escape(booking.vehicle_plate)}, "
            f"{status_label(booking.status)}, {services}"
        )
    return "\n".join(lines)
