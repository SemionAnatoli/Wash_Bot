from datetime import datetime
from decimal import Decimal

from app.services.customer_booking import ServiceOption

START_TEXT = "Здравствуйте! Помогу записаться на автомойку."
CHOOSE_SERVICE_TEXT = "Выберите основную услугу:"
CHOOSE_ADDONS_TEXT = "Выберите дополнительные услуги:"
CHOOSE_DATE_TEXT = "Выберите дату записи:"
CHOOSE_SLOT_TEXT = "Выберите свободное время:"
ASK_NAME_TEXT = "Введите ваше имя:"
ASK_PHONE_TEXT = "Введите номер телефона:"
ASK_VEHICLE_PLATE_TEXT = "Введите госномер автомобиля:"
NO_SERVICES_TEXT = "Сейчас нет доступных услуг для записи."
NO_SLOTS_TEXT = "На выбранную дату нет свободного времени."
INVALID_PHONE_TEXT = "Не удалось распознать номер телефона. Попробуйте еще раз."
INVALID_PLATE_TEXT = "Не удалось распознать госномер. Попробуйте еще раз."
SLOT_STALE_TEXT = "Это время уже недоступно. Выберите другой слот."
GENERIC_ERROR_TEXT = "Что-то пошло не так. Попробуйте позже."
CONFIRMED_TEXT = "Запись подтверждена."
PENDING_TEXT = "Заявка на запись отправлена и ожидает подтверждения."


def format_money(amount: Decimal) -> str:
    normalized = amount.normalize()
    if normalized == normalized.to_integral():
        text = str(normalized.quantize(Decimal("1")))
    else:
        text = format(amount, "f")
    return f"{text} руб."


def format_duration(duration_minutes: int) -> str:
    hours, minutes = divmod(duration_minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} ч")
    if minutes or not parts:
        parts.append(f"{minutes} мин")
    return " ".join(parts)


def service_line(service: ServiceOption) -> str:
    return (
        f"{service.title} — {format_money(service.price)}, "
        f"{format_duration(service.duration_minutes)}"
    )


def format_booking_summary(
    *,
    main_service: ServiceOption,
    addons: list[ServiceOption],
    start_at: datetime,
    customer_name: str,
    customer_phone: str,
    vehicle_plate: str,
) -> str:
    services = [main_service, *addons]
    total_price = sum((service.price for service in services), start=Decimal("0"))
    total_duration = sum(service.duration_minutes for service in services)
    addon_lines = (
        "\n".join(f"- {service_line(addon)}" for addon in addons) or "Без дополнительных услуг"
    )

    return (
        "Проверьте данные записи:\n"
        f"Услуга: {service_line(main_service)}\n"
        f"Дополнительно:\n{addon_lines}\n"
        f"Дата и время: {start_at:%d.%m.%Y %H:%M}\n"
        f"Имя: {customer_name}\n"
        f"Телефон: {customer_phone}\n"
        f"Автомобиль: {vehicle_plate}\n"
        f"Итого: {format_money(total_price)}\n"
        f"Длительность: {format_duration(total_duration)}"
    )
