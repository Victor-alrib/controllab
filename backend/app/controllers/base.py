"""Controller interface.

A controller is a *discrete-time* algorithm executed once per sampling period
Ts. The engine calls, in order, at every sampling instant t_k = k·Ts:

    u_cmd = controller.compute(ctx)      # ctx carries r_k, y_k (measured), x_k, ...
    u_sat = clip(u_cmd, u_min, u_max)    # actuator saturation (engine)
    controller.commit(u_sat)             # lets the controller track the applied input

``commit`` is what makes correct anti-windup possible (and, in the future,
is also where adaptive/observer-based laws update their internal state).

Extension points for the planned advanced controllers
-----------------------------------------------------
* ``requires_state``: LQR (and state-based SMC surfaces) need the plant state.
  The engine always fills ``ctx.x`` with the *true* plant state; a future
  observer (e.g. Luenberger / Kalman) can replace it transparently.
* ``is_linear`` / ``transfer_functions``: linear controllers expose their exact
  2-DOF transfer functions so that the analysis module can compute closed-loop
  poles, margins and Bode plots. Non-linear laws (SMC, Super-Twisting) return
  ``None`` and the analysis module reports that linear analysis does not apply.
* ``status = "planned"`` entries are listed in the catalogue so the UI can
  show the roadmap, but they cannot be instantiated.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

import control
import numpy as np

from app.core.params import ParamSpec, coerce_params


@dataclass
class ControllerInit:
    Ts: float
    r_init: float          # reference value just before t = 0
    y_init: float          # measured output at t = 0
    u_min: float | None
    u_max: float | None


@dataclass
class ControllerContext:
    k: int
    t: float
    r: float
    y: float               # measured output (with noise / output disturbance)
    x: np.ndarray          # true plant state (for state-feedback laws)
    Ts: float


Domain = Literal["continuous", "discrete"]


class Controller(ABC):
    type_id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    equation: ClassVar[str] = ""
    param_specs: ClassVar[list[ParamSpec]]
    status: ClassVar[str] = "available"
    requires_state: ClassVar[bool] = False
    is_linear: ClassVar[bool] = True

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = coerce_params(self.param_specs, params)

    @abstractmethod
    def reset(self, init: ControllerInit) -> None: ...

    @abstractmethod
    def compute(self, ctx: ControllerContext) -> float: ...

    def commit(self, u_applied: float) -> None:  # noqa: B027 - optional hook
        """Called with the saturated control actually applied to the plant."""

    def transfer_functions(
        self, domain: Domain, Ts: float | None = None
    ) -> tuple[control.TransferFunction, control.TransferFunction] | None:
        """Return (C_r, C_y) such that U = C_r·R − C_y·Y, or None if non-linear.

        For ``domain='discrete'`` the functions must be the *exact* z-domain
        description of the implemented difference equations.
        """
        return None

    @classmethod
    def describe(cls) -> dict[str, Any]:
        return {
            "type": cls.type_id,
            "name": cls.name,
            "description": cls.description,
            "equation": cls.equation,
            "status": cls.status,
            "requires_state": cls.requires_state,
            "is_linear": cls.is_linear,
            "params": [p.to_dict() for p in cls.param_specs],
        }


@dataclass(frozen=True)
class PlannedController:
    """Catalogue placeholder: documented in the roadmap, intentionally *not* implemented."""

    type_id: str
    name: str
    description: str
    requires_state: bool
    is_linear: bool

    def describe(self) -> dict[str, Any]:
        return {
            "type": self.type_id,
            "name": self.name,
            "description": self.description,
            "equation": "",
            "status": "planned",
            "requires_state": self.requires_state,
            "is_linear": self.is_linear,
            "params": [],
        }
