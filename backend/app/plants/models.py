"""Concrete linear plant models."""
from __future__ import annotations

import numpy as np
from scipy import signal

from app.core.params import ParamError, ParamSpec
from app.plants.base import DELAY_SPEC, PlantModel


class FirstOrderPlant(PlantModel):
    type_id = "first_order"
    name = "Primeira ordem"
    description = "G(s) = K / (τs + 1). Ex.: circuito RC, nível de tanque, temperatura."
    equation = "G(s) = K / (τs + 1) · e^(−θs)"
    param_specs = [
        ParamSpec("K", "Ganho estático K", default=1.0, min=-1e6, max=1e6, step=0.1),
        ParamSpec(
            "tau", "Constante de tempo τ", unit="s", default=1.0, min=0.0,
            exclusive_min=True, max=1e5, step=0.1,
        ),
        ParamSpec(
            "y0", "Saída inicial y(0)", default=0.0, min=-1e6, max=1e6, step=0.1,
            group="Condições iniciais",
        ),
        DELAY_SPEC,
    ]

    def state_space(self):
        K, tau = self.params["K"], self.params["tau"]
        A = np.array([[-1.0 / tau]])
        B = np.array([[K / tau]])
        C = np.array([[1.0]])
        D = np.array([[0.0]])
        return A, B, C, D

    def initial_state(self):
        return np.array([self.params["y0"]])


class SecondOrderPlant(PlantModel):
    type_id = "second_order"
    name = "Segunda ordem"
    description = (
        "Forma canônica G(s) = K ωn² / (s² + 2ζωn s + ωn²). Ex.: massa-mola-amortecedor, "
        "motor CC com indutância, suspensão."
    )
    equation = "G(s) = K·ωn² / (s² + 2ζωn·s + ωn²) · e^(−θs)"
    param_specs = [
        ParamSpec("K", "Ganho estático K", default=1.0, min=-1e6, max=1e6, step=0.1),
        ParamSpec(
            "wn", "Frequência natural ωn", unit="rad/s", default=2.0, min=0.0,
            exclusive_min=True, max=1e5, step=0.1,
        ),
        ParamSpec(
            "zeta", "Coef. de amortecimento ζ", default=0.3, min=-10.0, max=100.0, step=0.05,
            description="ζ<0: instável; 0≤ζ<1: subamortecido; ζ=1: crítico; ζ>1: sobreamortecido.",
        ),
        ParamSpec(
            "y0", "Saída inicial y(0)", default=0.0, min=-1e6, max=1e6, step=0.1,
            group="Condições iniciais",
        ),
        ParamSpec(
            "dy0", "Derivada inicial ẏ(0)", unit="1/s", default=0.0, min=-1e6, max=1e6,
            step=0.1, group="Condições iniciais",
        ),
        DELAY_SPEC,
    ]

    def state_space(self):
        K, wn, z = self.params["K"], self.params["wn"], self.params["zeta"]
        # x1 = y, x2 = dy/dt  (phase-variable form, physically meaningful ICs)
        A = np.array([[0.0, 1.0], [-wn**2, -2.0 * z * wn]])
        B = np.array([[0.0], [K * wn**2]])
        C = np.array([[1.0, 0.0]])
        D = np.array([[0.0]])
        return A, B, C, D

    def initial_state(self):
        return np.array([self.params["y0"], self.params["dy0"]])


class TransferFunctionPlant(PlantModel):
    type_id = "transfer_function"
    name = "Função de transferência"
    description = (
        "G(s) = N(s)/D(s) arbitrária e própria (grau N ≤ grau D). Coeficientes em "
        "potências decrescentes de s. Condição inicial: repouso (x(0)=0)."
    )
    equation = "G(s) = (b_m·s^m + … + b₀) / (a_n·s^n + … + a₀) · e^(−θs)"
    param_specs = [
        ParamSpec("num", "Numerador N(s)", kind="vector", default=[1.0],
                  description="Ex.: [1, 2] representa s + 2."),
        ParamSpec("den", "Denominador D(s)", kind="vector", default=[1.0, 3.0, 2.0],
                  description="Ex.: [1, 3, 2] representa s² + 3s + 2."),
        DELAY_SPEC,
    ]

    def _validate(self):
        num = np.trim_zeros(self.params["num"], "f")
        den = np.trim_zeros(self.params["den"], "f")
        if den.size == 0:
            raise ParamError("O denominador não pode ser nulo.")
        if num.size == 0:
            num = np.array([0.0])
        if den.size < 2:
            raise ParamError("O denominador deve ter grau ≥ 1 (sistema dinâmico).")
        if num.size > den.size:
            raise ParamError("Função de transferência imprópria: grau(N) > grau(D).")
        if den.size > 21:
            raise ParamError("Ordem máxima suportada: 20.")
        self.params["num"], self.params["den"] = num, den

    def state_space(self):
        A, B, C, D = signal.tf2ss(self.params["num"], self.params["den"])
        return (np.atleast_2d(A), np.atleast_2d(B).reshape(-1, 1),
                np.atleast_2d(C).reshape(1, -1), np.atleast_2d(D).reshape(1, 1))


class StateSpacePlant(PlantModel):
    type_id = "state_space"
    name = "Espaço de estados"
    description = "ẋ = Ax + Bu, y = Cx + Du (SISO). Permite condição inicial x(0) arbitrária."
    equation = "ẋ = Ax + Bu(t−θ),   y = Cx + Du(t−θ)"
    param_specs = [
        ParamSpec("A", "Matriz A (n×n)", kind="matrix", default=[[0.0, 1.0], [-2.0, -3.0]]),
        ParamSpec("B", "Matriz B (n×1)", kind="matrix", default=[[0.0], [1.0]]),
        ParamSpec("C", "Matriz C (1×n)", kind="matrix", default=[[1.0, 0.0]]),
        ParamSpec("D", "Matriz D (1×1)", kind="matrix", default=[[0.0]]),
        ParamSpec("x0", "Estado inicial x(0)", kind="vector", default=[0.0, 0.0],
                  group="Condições iniciais"),
        DELAY_SPEC,
    ]

    def _validate(self):
        A, B, C, D = (self.params[k] for k in "ABCD")
        n = A.shape[0]
        if A.shape != (n, n) or n == 0:
            raise ParamError("A deve ser quadrada.")
        if n > 20:
            raise ParamError("Ordem máxima suportada: 20.")
        if B.shape == (1, n) and n > 1:
            B = B.T  # accept a row given for convenience
        if B.shape != (n, 1):
            raise ParamError(f"B deve ser {n}×1 (sistema SISO).")
        if C.shape != (1, n):
            raise ParamError(f"C deve ser 1×{n}.")
        if D.shape != (1, 1):
            raise ParamError("D deve ser 1×1.")
        x0 = self.params["x0"]
        if x0.size != n:
            raise ParamError(f"x(0) deve ter {n} elementos.")
        self.params["B"] = B

    def state_space(self):
        return tuple(np.array(self.params[k], dtype=float) for k in "ABCD")  # type: ignore[return-value]

    def initial_state(self):
        return np.array(self.params["x0"], dtype=float)
