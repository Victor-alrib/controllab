from __future__ import annotations

from typing import Any

from app.controllers.base import Controller, PlannedController
from app.controllers.pid import OpenLoopController, PController, PIController, PIDController
from app.core.params import ParamError

CONTROLLERS: dict[str, type[Controller]] = {
    cls.type_id: cls
    for cls in (OpenLoopController, PController, PIController, PIDController)
}

# Roadmap entries. They are shown in the UI as "em desenvolvimento" and are
# deliberately NOT implemented (not even in simplified form).
PLANNED: list[PlannedController] = [
    PlannedController(
        "lqr", "LQR",
        "Regulador linear quadrático: u = −Kx + N̄r, K de Riccati (Q, R). Requer acesso ao estado.",
        requires_state=True, is_linear=True,
    ),
    PlannedController(
        "smc", "Modos Deslizantes (SMC)",
        "Superfície deslizante σ(x) e lei de alcançabilidade descontínua; robusto a perturbações "
        "casadas. Exige análise de chattering e taxa de amostragem adequada.",
        requires_state=True, is_linear=False,
    ),
    PlannedController(
        "st_smc", "Super-Twisting (ST-SMC)",
        "Algoritmo de 2ª ordem: u = −k₁|σ|^{1/2}sign(σ) + v, v̇ = −k₂ sign(σ). Controle contínuo, "
        "convergência em tempo finito.",
        requires_state=True, is_linear=False,
    ),
]


def build_controller(type_id: str, params: dict[str, Any] | None) -> Controller:
    if type_id in {p.type_id for p in PLANNED}:
        raise ParamError(f"O controlador '{type_id}' está planejado e ainda não foi implementado.")
    try:
        cls = CONTROLLERS[type_id]
    except KeyError:
        raise ParamError(f"Controlador desconhecido: '{type_id}'.") from None
    return cls(params)


def controller_catalog() -> list[dict[str, Any]]:
    return [c.describe() for c in CONTROLLERS.values()] + [p.describe() for p in PLANNED]
