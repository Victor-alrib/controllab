"""Base class for plant models.

All plants are SISO, continuous-time, linear time-invariant systems written as

    dx/dt = A x + B u(t - θ)
        y = C x + D u(t - θ)

where θ ≥ 0 is an optional pure input (transport) delay. The simulation engine
integrates this model *exactly* (zero-order-hold discretisation through the
matrix exponential), so no numerical integration error is introduced between
sampling instants as long as the input is piecewise constant — which is the
case for a digital controller followed by a ZOH actuator.

To add a new plant: subclass ``PlantModel``, declare ``param_specs`` and
implement ``state_space`` (and ``initial_state`` when the model has a natural
notion of initial conditions). Then register it in ``plants/registry.py``.
Non-linear plants will require a different integration path; see
``docs/ARQUITETURA.md``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import control
import numpy as np

from app.core.params import ParamSpec, coerce_params

DELAY_SPEC = ParamSpec(
    key="delay",
    label="Atraso de transporte θ",
    unit="s",
    default=0.0,
    min=0.0,
    max=1e4,
    step=0.01,
    group="Atraso",
    advanced=True,
    description=(
        "Atraso puro na entrada da planta, e^{-θs}. Na simulação é exato quando θ é "
        "múltiplo do passo de integração; caso contrário é arredondado (o valor efetivo "
        "é informado). Na análise linear usa-se aproximação de Padé."
    ),
)


class PlantModel(ABC):
    type_id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    equation: ClassVar[str] = ""
    param_specs: ClassVar[list[ParamSpec]]

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = coerce_params(self.param_specs, params)
        self._validate()

    # ------------------------------------------------------------------ hooks
    def _validate(self) -> None:
        """Model-specific consistency checks (raise ParamError)."""

    @abstractmethod
    def state_space(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return continuous-time (A, B, C, D) with shapes (n,n),(n,1),(1,n),(1,1)."""

    def initial_state(self) -> np.ndarray:
        A, *_ = self.state_space()
        return np.zeros(A.shape[0])

    # ---------------------------------------------------------------- helpers
    @property
    def delay(self) -> float:
        return float(self.params.get("delay", 0.0))

    def lti(self) -> control.StateSpace:
        A, B, C, D = self.state_space()
        return control.ss(A, B, C, D)

    def transfer_function(self) -> control.TransferFunction:
        """Rational part G(s) (delay excluded).

        ss→tf conversion leaves round-off residues (~1e-16) in the leading
        numerator coefficients, which would appear as spurious zeros at
        ~1e16. They are removed with a relative tolerance before minreal.
        """
        tf = control.ss2tf(self.lti())
        num = np.atleast_1d(np.squeeze(tf.num[0][0])).astype(float)
        den = np.atleast_1d(np.squeeze(tf.den[0][0])).astype(float)
        tol = 1e-10 * max(np.max(np.abs(num)), np.max(np.abs(den)))
        num[np.abs(num) < tol] = 0.0
        num = np.trim_zeros(num, "f")
        if num.size == 0:
            num = np.array([0.0])
        return control.minreal(control.tf(num, den), tol=1e-9, verbose=False)

    @classmethod
    def describe(cls) -> dict[str, Any]:
        return {
            "type": cls.type_id,
            "name": cls.name,
            "description": cls.description,
            "equation": cls.equation,
            "params": [p.to_dict() for p in cls.param_specs],
        }
