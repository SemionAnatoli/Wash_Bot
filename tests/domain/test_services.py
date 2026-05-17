import pytest

from app.domain.errors import ValidationError
from app.domain.services import SelectedService, calculate_total_duration


def test_calculate_total_duration_adds_main_service_and_addons() -> None:
    main = SelectedService(id=1, title="Standard", duration_minutes=60, is_addon=False)
    addons = [
        SelectedService(id=2, title="Wax", duration_minutes=15, is_addon=True),
        SelectedService(id=3, title="Tires", duration_minutes=10, is_addon=True),
    ]

    assert calculate_total_duration(main, addons) == 85


def test_calculate_total_duration_rejects_addon_as_main_service() -> None:
    main = SelectedService(id=2, title="Wax", duration_minutes=15, is_addon=True)

    with pytest.raises(ValidationError):
        calculate_total_duration(main, [])


def test_calculate_total_duration_rejects_non_addon_in_addons() -> None:
    main = SelectedService(id=1, title="Standard", duration_minutes=60, is_addon=False)
    addons = [SelectedService(id=4, title="Full", duration_minutes=90, is_addon=False)]

    with pytest.raises(ValidationError):
        calculate_total_duration(main, addons)


def test_calculate_total_duration_rejects_invalid_duration() -> None:
    main = SelectedService(id=1, title="Standard", duration_minutes=0, is_addon=False)

    with pytest.raises(ValidationError):
        calculate_total_duration(main, [])
