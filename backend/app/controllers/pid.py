"""Open-loop and discrete PID family (P, PI, PID).

Continuous-time reference law (parallel / "ideal-parallel" form, 2 DOF):

    u(t) = Kp·(b·r − y) + Ki·∫(r − y)dt + Kd · s/(Tf·s + 1) · (c·r − y)

Discrete implementation, executed every Ts (this is exactly what is simulated):

    P_k = Kp·(b·r_k − y_k)
    I   : forward Euler   I_k = I_{k−1} + Ki·Ts·e_{k−1}            → Ki·Ts/(z−1)
          backward Euler  I_k = I_{k−1} + Ki·Ts·e_k                → Ki·Ts·z/(z−1)
          Tustin          I_k = I_{k−1} + Ki·Ts·(e_k + e_{k−1})/2  → Ki·Ts(z+1)/(2(z−1))
    D_k = [Tf·D_{k−1} + Kd·(ed_k − ed_{k−1})] / (Tf + Ts),  ed = c·r − y
          (backward-Euler discretisation of Kd·s/(Tf·s+1) → Kd(z−1)/((Tf+Ts)z − Tf))
    u_k = P_k + I_k + D_k

Anti-windup (active only when the actuator saturates):
    * clamping (integração condicional): the integrator does not integrate when
      the actuator is saturated and the error would push it further in.
    * back-calculation: I ← I + Kt·Ts·(u_sat − u_cmd)   (Åström & Hägglund).
"""
from __future__ import annotations

from typing import Any

import control
import numpy as np

from app.controllers.base import Controller, ControllerContext, ControllerInit, Domain
from app.core.params import ParamSpec

S = control.tf("s")


def _z(Ts: float) -> control.TransferFunction:
    return control.tf([1.0, 0.0], [1.0], Ts)


class OpenLoopController(Controller):
    type_id = "open_loop"
    name = "Malha aberta"
    description = (
        "u(t) = Kff·r(t). Sem realimentação: não corrige perturbações nem erros de modelo. "
        "Para seguimento exato de degrau use Kff = 1/G(0)."
    )
    equation = "u_k = Kff · r_k"
    param_specs = [
        ParamSpec("Kff", "Ganho de alimentação direta Kff", default=1.0, min=-1e6, max=1e6,
                  step=0.1),
    ]

    def reset(self, init: ControllerInit) -> None:
        pass

    def compute(self, ctx: ControllerContext) -> float:
        return self.params["Kff"] * ctx.r

    def transfer_functions(self, domain: Domain, Ts: float | None = None):
        dt = Ts if domain == "discrete" else 0
        return (control.tf([self.params["Kff"]], [1.0], dt), control.tf([0.0], [1.0], dt))


_INTEGRATION_OPTIONS = [
    {"value": "forward", "label": "Euler progressivo"},
    {"value": "backward", "label": "Euler regressivo"},
    {"value": "tustin", "label": "Tustin (trapezoidal)"},
]
_AW_OPTIONS = [
    {"value": "none", "label": "Nenhum"},
    {"value": "clamping", "label": "Integração condicional (clamping)"},
    {"value": "back_calculation", "label": "Back-calculation"},
]

_SPEC = {
    "Kp": ParamSpec("Kp", "Ganho proporcional Kp", default=1.0, min=-1e6, max=1e6, step=0.1,
                    group="Ganhos"),
    "Ki": ParamSpec("Ki", "Ganho integral Ki", unit="1/s", default=0.5, min=0.0, max=1e6,
                    step=0.05, group="Ganhos"),
    "Kd": ParamSpec("Kd", "Ganho derivativo Kd", unit="s", default=0.1, min=0.0, max=1e6,
                    step=0.01, group="Ganhos"),
    "Tf": ParamSpec(
        "Tf", "Filtro derivativo Tf", unit="s", default=0.01, min=0.0, max=1e4, step=0.001,
        group="Derivativo", advanced=True,
        description="Constante de tempo do filtro passa-baixas do termo D: Kd·s/(Tf·s+1). "
                    "Tf = 0 → derivada pura (diferença regressiva).",
    ),
    "b": ParamSpec(
        "b", "Peso de referência no P (b)", default=1.0, min=0.0, max=1.0, step=0.05,
        group="Estrutura 2-GDL", advanced=True,
        description="b = 1: P sobre o erro; b < 1 reduz o overshoot ao degrau sem alterar os polos.",
    ),
    "c": ParamSpec(
        "c", "Peso de referência no D (c)", default=1.0, min=0.0, max=1.0, step=0.05,
        group="Estrutura 2-GDL", advanced=True,
        description="c = 0: derivada apenas da medição (elimina o 'derivative kick').",
    ),
    "integration": ParamSpec(
        "integration", "Discretização do integrador", kind="select", default="forward",
        options=_INTEGRATION_OPTIONS, group="Discretização", advanced=True,
    ),
    "anti_windup": ParamSpec(
        "anti_windup", "Anti-windup", kind="select", default="back_calculation",
        options=_AW_OPTIONS, group="Anti-windup", advanced=True,
        description="Só tem efeito quando a saturação do atuador está ativa.",
    ),
    "Kt": ParamSpec(
        "Kt", "Ganho de rastreamento Kt", unit="1/s", default=1.0, min=0.0, max=1e6, step=0.1,
        group="Anti-windup", advanced=True,
        description="Usado no back-calculation. Regra prática: Kt = 1/√(Ti·Td).",
    ),
}


class PIDController(Controller):
    type_id = "pid"
    name = "PID"
    description = "PID discreto paralelo com filtro derivativo, pesos de referência e anti-windup."
    equation = "u = Kp·(b·r − y) + Ki·∫e dt + Kd·s/(Tf·s + 1)·(c·r − y)"
    param_specs = [_SPEC[k] for k in ("Kp", "Ki", "Kd", "Tf", "b", "c", "integration",
                                       "anti_windup", "Kt")]
    # Values used for parameters not exposed by a reduced variant (P, PI).
    fixed_params: dict[str, Any] = {}

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        full = {
            "Kp": 0.0, "Ki": 0.0, "Kd": 0.0, "Tf": 0.0, "b": 1.0, "c": 1.0,
            "integration": "forward", "anti_windup": "none", "Kt": 0.0,
        }
        full.update(self.fixed_params)
        full.update(self.params)
        self.p = full

    # ----------------------------------------------------------- simulation
    def reset(self, init: ControllerInit) -> None:
        self.Ts = init.Ts
        self.u_min, self.u_max = init.u_min, init.u_max
        self.I = 0.0
        self.D = 0.0
        self.e_prev = init.r_init - init.y_init
        self.ed_prev = self.p["c"] * init.r_init - init.y_init
        self._pending: tuple[float, float, float] | None = None

    def compute(self, ctx: ControllerContext) -> float:
        p, Ts = self.p, self.Ts
        e = ctx.r - ctx.y
        P = p["Kp"] * (p["b"] * ctx.r - ctx.y)

        method = p["integration"]
        if method == "forward":
            inc_now, inc_next = 0.0, p["Ki"] * Ts * e
        elif method == "backward":
            inc_now, inc_next = p["Ki"] * Ts * e, 0.0
        else:  # tustin
            inc_now, inc_next = p["Ki"] * Ts * 0.5 * (e + self.e_prev), 0.0
        I_used = self.I + inc_now

        ed = p["c"] * ctx.r - ctx.y
        if p["Kd"] != 0.0:
            self.D = (p["Tf"] * self.D + p["Kd"] * (ed - self.ed_prev)) / (p["Tf"] + Ts)
        else:
            self.D = 0.0
        self.ed_prev = ed
        self.e_prev = e

        u = P + I_used + self.D
        self._pending = (u, inc_now + inc_next, e)
        return u

    def commit(self, u_applied: float) -> None:
        assert self._pending is not None
        u_cmd, increment, e = self._pending
        aw = self.p["anti_windup"]
        saturated = u_applied != u_cmd
        if aw == "clamping" and saturated and (
            (u_cmd > u_applied and e * np.sign(self.p["Ki"]) > 0)
            or (u_cmd < u_applied and e * np.sign(self.p["Ki"]) < 0)
        ):
            increment = 0.0
        self.I += increment
        if aw == "back_calculation" and saturated:
            self.I += self.p["Kt"] * self.Ts * (u_applied - u_cmd)
        self._pending = None

    # ------------------------------------------------------- linear analysis
    def transfer_functions(self, domain: Domain, Ts: float | None = None):
        p = self.p
        Kp, Ki, Kd, Tf, b, c = (p[k] for k in ("Kp", "Ki", "Kd", "Tf", "b", "c"))
        if domain == "continuous":
            I = control.tf([1.0], [1.0, 0.0])
            D = control.tf([1.0, 0.0], [Tf, 1.0]) if Tf > 0 else control.tf([1.0, 0.0], [1.0])
            one = control.tf([1.0], [1.0])
        else:
            assert Ts is not None and Ts > 0
            z = _z(Ts)
            one = control.tf([1.0], [1.0], Ts)
            I = {
                "forward": Ts / (z - 1),
                "backward": Ts * z / (z - 1),
                "tustin": Ts * (z + 1) / (2 * (z - 1)),
            }[p["integration"]]
            D = (z - 1) / ((Tf + Ts) * z - Tf)
        Cr = Kp * b * one
        Cy = Kp * one
        if Ki != 0:
            Cr = Cr + Ki * I
            Cy = Cy + Ki * I
        if Kd != 0:
            Cr = Cr + Kd * c * D
            Cy = Cy + Kd * D
        return (control.minreal(Cr, tol=1e-10, verbose=False),
                control.minreal(Cy, tol=1e-10, verbose=False))


class PController(PIDController):
    type_id = "p"
    name = "P"
    description = "Controle proporcional u = Kp·e. Erro em regime ao degrau ≠ 0 para plantas tipo 0."
    equation = "u_k = Kp · e_k"
    param_specs = [_SPEC["Kp"]]
    fixed_params = {"Ki": 0.0, "Kd": 0.0, "anti_windup": "none"}


class PIController(PIDController):
    type_id = "pi"
    name = "PI"
    description = "Controle proporcional-integral: elimina erro em regime ao degrau (planta tipo 0)."
    equation = "u = Kp·(b·r − y) + Ki·∫e dt"
    param_specs = [_SPEC[k] for k in ("Kp", "Ki", "b", "integration", "anti_windup", "Kt")]
    fixed_params = {"Kd": 0.0}
