ADMIN_TODAY_CALLBACK = "admin:today"


def build_admin_confirm_callback(booking_id: int) -> str:
    return f"admin:confirm:{booking_id}"


def build_admin_cancel_callback(booking_id: int) -> str:
    return f"admin:cancel:{booking_id}"


def parse_admin_booking_id(data: str, *, prefix: str) -> int:
    expected_prefix = f"{prefix}:"
    if not data.startswith(expected_prefix):
        raise ValueError("Unexpected admin callback prefix.")
    return int(data.removeprefix(expected_prefix))
