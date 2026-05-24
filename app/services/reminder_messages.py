from datetime import datetime


def format_booking_reminder_text(start_at: datetime) -> str:
    return (
        f"Напоминание: вы записаны на автомойку {start_at:%d.%m.%Y} в {start_at:%H:%M}. "
        "Если планы изменились, откройте бота и отмените запись заранее."
    )
