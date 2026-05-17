from dataclasses import dataclass

from app.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class SelectedService:
    id: int
    title: str
    duration_minutes: int
    is_addon: bool


def _validate_duration(duration_minutes: int) -> None:
    if duration_minutes <= 0 or duration_minutes > 480:
        raise ValidationError("Service duration must be between 1 and 480 minutes.")


def calculate_total_duration(main_service: SelectedService, addons: list[SelectedService]) -> int:
    if main_service.is_addon:
        raise ValidationError("Main service cannot be an add-on.")
    _validate_duration(main_service.duration_minutes)

    total = main_service.duration_minutes
    for addon in addons:
        if not addon.is_addon:
            raise ValidationError("Add-on list cannot contain main services.")
        _validate_duration(addon.duration_minutes)
        total += addon.duration_minutes

    if total > 480:
        raise ValidationError("Total booking duration cannot exceed 480 minutes.")
    return total
