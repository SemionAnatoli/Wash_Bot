import pytest

from app.domain.errors import ValidationError
from app.domain.validation import normalize_name, normalize_phone, normalize_vehicle_plate


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Иван", "Иван"),
        ("  Ivan Petrov  ", "Ivan Petrov"),
    ],
)
def test_normalize_name_accepts_valid_names(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "A", "x" * 81])
def test_normalize_name_rejects_invalid_names(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalize_name(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+7 913 123-45-67", "+79131234567"),
        ("8 (913) 123-45-67", "+79131234567"),
    ],
)
def test_normalize_phone_accepts_russian_formats(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "123", "+1 555 000 00 00", "8913123456"])
def test_normalize_phone_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalize_phone(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("а123вс154", "А123ВС154"),
        (" A 123 BC 154 ", "A 123 BC 154"),
    ],
)
def test_normalize_vehicle_plate_accepts_soft_plate_format(raw: str, expected: str) -> None:
    assert normalize_vehicle_plate(raw) == expected


@pytest.mark.parametrize("raw", ["", " ", "!", "x" * 16])
def test_normalize_vehicle_plate_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(ValidationError):
        normalize_vehicle_plate(raw)
