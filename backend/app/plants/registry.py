from __future__ import annotations

from typing import Any

from app.core.params import ParamError
from app.plants.base import PlantModel
from app.plants.models import (
    FirstOrderPlant,
    SecondOrderPlant,
    StateSpacePlant,
    TransferFunctionPlant,
)

PLANTS: dict[str, type[PlantModel]] = {
    cls.type_id: cls
    for cls in (FirstOrderPlant, SecondOrderPlant, TransferFunctionPlant, StateSpacePlant)
}


def build_plant(type_id: str, params: dict[str, Any] | None) -> PlantModel:
    try:
        cls = PLANTS[type_id]
    except KeyError:
        raise ParamError(f"Planta desconhecida: '{type_id}'.") from None
    return cls(params)


def plant_catalog() -> list[dict[str, Any]]:
    return [cls.describe() for cls in PLANTS.values()]
