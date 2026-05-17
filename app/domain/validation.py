import re

from app.domain.errors import ValidationError

_PLATE_PATTERN = re.compile(r"^[0-9A-ZА-ЯЁ -]+$")


def normalize_name(raw: str) -> str:
    value = " ".join(raw.strip().split())
    if len(value) < 2 or len(value) > 80:
        raise ValidationError("Name must be between 2 and 80 characters.")
    return value


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        raise ValidationError("Phone must be a valid Russian number.")
    return f"+{digits}"


def normalize_vehicle_plate(raw: str) -> str:
    value = " ".join(raw.strip().upper().split())
    if len(value) < 2 or len(value) > 15:
        raise ValidationError("Vehicle plate must be between 2 and 15 characters.")
    if not _PLATE_PATTERN.fullmatch(value):
        raise ValidationError("Vehicle plate contains unsupported characters.")
    return value
