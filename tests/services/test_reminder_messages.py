from datetime import datetime

from app.services.reminder_messages import format_booking_reminder_text


def test_format_booking_reminder_text_contains_core_reminder_details() -> None:
    text = format_booking_reminder_text(datetime(2026, 5, 30, 19, 0))

    assert text.startswith("Напоминание:")
    assert "30.05.2026" in text
    assert "19:00" in text
    assert "автомойку" in text
    assert "откройте бота" in text
    assert "отмените запись заранее" in text
