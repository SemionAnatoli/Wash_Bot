from datetime import datetime

BOOKING_START_CALLBACK = "book:start"
ADDONS_DONE_CALLBACK = "book:addons_done"
CONFIRM_BOOKING_CALLBACK = "book:confirm"
CHANGE_SERVICES_CALLBACK = "book:change_services"
CHANGE_TIME_CALLBACK = "book:change_time"
CANCEL_FLOW_CALLBACK = "book:cancel_flow"


def build_main_service_callback(service_id: int) -> str:
    return f"book:main:{service_id}"


def build_addon_callback(service_id: int) -> str:
    return f"book:addon:{service_id}"


def build_date_callback(day: str) -> str:
    return f"book:date:{day}"


def build_slot_callback(start_at: datetime) -> str:
    return f"book:slot:{start_at.strftime('%Y-%m-%dT%H:%M')}"


def parse_id_callback(data: str, *, prefix: str) -> int:
    expected_prefix = f"{prefix}:"
    if not data.startswith(expected_prefix):
        raise ValueError("Unexpected callback prefix.")
    return int(data.removeprefix(expected_prefix))


def parse_date_callback(data: str) -> str:
    prefix = "book:date:"
    if not data.startswith(prefix):
        raise ValueError("Unexpected date callback prefix.")
    return data.removeprefix(prefix)


def parse_slot_callback(data: str) -> datetime:
    prefix = "book:slot:"
    if not data.startswith(prefix):
        raise ValueError("Unexpected slot callback prefix.")
    return datetime.fromisoformat(data.removeprefix(prefix))
