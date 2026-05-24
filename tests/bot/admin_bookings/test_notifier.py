from dataclasses import dataclass, field
from typing import Any

import pytest

from app.bot.admin_bookings.notifier import AdminBookingNotifier, AdminNotificationError
from tests.bot.admin_bookings.fakes import booking_details


@dataclass
class FakeBot:
    failing_admin_ids: set[int] = field(default_factory=set)
    sent_messages: list[dict[str, Any]] = field(default_factory=list)

    async def send_message(self, chat_id: int, text: str, reply_markup: Any = None) -> None:
        if chat_id in self.failing_admin_ids:
            raise RuntimeError("Telegram failed.")
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )


@dataclass
class FakeAdminBookingService:
    details_requests: list[dict[str, int]] = field(default_factory=list)

    async def get_booking_details(self, *, car_wash_id: int, booking_id: int):
        self.details_requests.append({"car_wash_id": car_wash_id, "booking_id": booking_id})
        return booking_details(booking_id=booking_id)


async def test_notifier_returns_without_work_when_no_admins() -> None:
    bot = FakeBot()
    service = FakeAdminBookingService()
    notifier = AdminBookingNotifier(
        bot=bot,
        admin_booking_service=service,
        admin_telegram_ids=(),
    )

    await notifier.notify_new_booking(car_wash_id=10, booking_id=42)

    assert service.details_requests == []
    assert bot.sent_messages == []


async def test_notifier_sends_booking_details_to_each_admin() -> None:
    bot = FakeBot()
    service = FakeAdminBookingService()
    notifier = AdminBookingNotifier(
        bot=bot,
        admin_booking_service=service,
        admin_telegram_ids=(1001, 1002),
    )

    await notifier.notify_new_booking(car_wash_id=10, booking_id=42)

    assert service.details_requests == [{"car_wash_id": 10, "booking_id": 42}]
    assert [message["chat_id"] for message in bot.sent_messages] == [1001, 1002]
    assert "Новая запись" in bot.sent_messages[0]["text"]
    assert "#42" in bot.sent_messages[0]["text"]
    assert bot.sent_messages[0]["reply_markup"] is not None


async def test_notifier_raises_notification_error_after_send_failure() -> None:
    bot = FakeBot(failing_admin_ids={1001})
    service = FakeAdminBookingService()
    notifier = AdminBookingNotifier(
        bot=bot,
        admin_booking_service=service,
        admin_telegram_ids=(1001, 1002),
    )

    with pytest.raises(AdminNotificationError):
        await notifier.notify_new_booking(car_wash_id=10, booking_id=42)

    assert [message["chat_id"] for message in bot.sent_messages] == [1002]
