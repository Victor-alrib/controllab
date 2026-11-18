"""Sampled-data closed-loop simulation engine.

Loop structure (digital control of a continuous plant):

          r_k ┌────────────┐ u_cmd ┌─────┐ u_k  ┌───┐   d_in(t)      ┌────────┐ y_p   d_out(t)
    r(t) ─S──►│ controller │──────►│ sat │─────►│ZOH│──►(+)──► e^{-θs}│ planta │──►(+)──► y(t)
              └────────────┘       └─────┘      └───┘                 └────────┘
                   ▲  y_k = y(t_k) + n_k   (measurement noise)                         │
                   └─────────────────────────────────S─────────────────────────────────┘

Exactness: between sampling instants the plant input is piecewise constant
(ZOH output plus disturbance evaluated on a finer sub-grid of step h = Ts/n_sub),
and the plant is propagated with the exact ZOH transition matrices

    Φ = e^{A h},   Γ = ∫₀^h e^{A τ} dτ · B

computed by the matrix exponential of the augmented matrix [[A, B],[0, 0]]·h.
The only approximations are therefore (i) disturbances that vary *within* a
sub-step are sampled at its start and (ii) a transport delay that is not a
multiple of h is rounded to the nearest multiple (reported in ``warnings``).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.linalg import expm

from app.controllers.base import ControllerContext, ControllerInit
from app.controllers.registry import build_controller
from app.core.params import ParamError
from app.plants.registry import build_plant
from app.schemas import SimulationRequest
from app.simulation.metrics import control_metrics, integral_metrics, step_metrics
from app.simulation.signals import disturbance_signal, reference_signal, sum_signals

MAX_SAMPLES = 200_000
TARGET_FINE_POINTS = 20_000
MAX_SUBSTEPS = 50


def zoh_discretize(A: np.ndarray, B: np.ndarray, h: float) -> tuple[np.ndarray, np.ndarray]:
    n, m = A.shape[0], B.shape[1]
    M = np.zeros((n + m, n + m))
    M[:n, :n] = A * h
    M[:n, n:] = B * h
    E = expm(M)
    return E[:n, :n], E[:n, n:]


@dataclass
class SimulationResult:
    t: np.ndarray
    r: np.ndarray
    y: np.ndarray
    e: np.ndarray
    u: np.ndarray
    u_cmd: np.ndarray
    d_in: np.ndarray
    d_out: np.ndarray
    t_k: np.ndarray
    r_k: np.ndarray
    y_meas_k: np.ndarray
    u_k: np.ndarray
    u_cmd_k: np.ndarray
    metrics: dict[str, Any]
    meta: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def _sanitize(a: np.ndarray) -> list[float | None]:
    """JSON has no NaN/Inf: map them to None (unstable runs may overflow)."""
    return [float(v) if math.isfinite(v) else None for v in a.tolist()]


def simulate(req: SimulationRequest) -> SimulationResult:
    s = req.settings
    plant = build_plant(req.plant.type, req.plant.params)
    ctrl = build_controller(req.controller.type, req.controller.params)

    Ts, tf = s.Ts, s.t_final
    N = int(round(tf / Ts))
    warnings: list[str] = []
    if N < 2:
        raise ParamError("O tempo de simulação deve conter pelo menos 2 períodos de amostragem.")
    if N > MAX_SAMPLES:
        raise ParamError(
            f"Número de amostras ({N}) excede o limite ({MAX_SAMPLES}). Aumente Ts ou reduza o tempo."
        )
    if abs(N * Ts - tf) > 1e-9 * max(1.0, tf):
        warnings.append(f"Tempo final ajustado para {N * Ts:g} s (múltiplo de Ts).")

    n_sub = int(max(1, min(MAX_SUBSTEPS, TARGET_FINE_POINTS // N)))
    h = Ts / n_sub

    A, B, C, D = plant.state_space()
    Phi, Gam = zoh_discretize(A, B, h)
    C1, D1 = C.reshape(-1), float(D.reshape(-1)[0])
    x = plant.initial_state().astype(float).copy()

    # Fastest open-loop mode vs. sampling (educational warning, Nyquist-like rule).
    eig = np.linalg.eigvals(A)
    if eig.size:
        fastest = float(np.max(np.abs(eig)))
        if fastest > 0 and Ts > 1.0 / fastest:
            warnings.append(
                f"Ts = {Ts:g} s é grande comparado ao modo mais rápido da planta "
                f"(|λ|máx = {fastest:.3g} rad/s). Considere Ts ≤ {0.1 / fastest:.3g} s."
            )

    delay_steps = int(round(plant.delay / h))
    delay_eff = delay_steps * h
    if plant.delay > 0 and abs(delay_eff - plant.delay) > 1e-9 * max(1.0, plant.delay):
        warnings.append(
            f"Atraso arredondado de {plant.delay:g} s para {delay_eff:g} s (múltiplo de h = {h:g} s)."
        )
    buf: deque[float] = deque([0.0] * delay_steps)

    ref = reference_signal(req.reference)
    d_in_sig = sum_signals([disturbance_signal(d) for d in req.disturbances if d.target == "input"])
    d_out_sig = sum_signals([disturbance_signal(d) for d in req.disturbances if d.target == "output"])
    rng = np.random.default_rng(req.noise.seed)
    noise_std = req.noise.std if req.noise.enabled else 0.0
    sat = req.saturation
    u_lo = sat.u_min if sat.enabled else -np.inf
    u_hi = sat.u_max if sat.enabled else np.inf

    M = N * n_sub + 1
    t_f = np.arange(M) * h
    y_f = np.empty(M); r_f = np.empty(M); u_f = np.empty(M); uc_f = np.empty(M)
    di_f = np.empty(M); do_f = np.empty(M)
    t_k = np.arange(N) * Ts
    r_k = np.empty(N); ym_k = np.empty(N); u_k = np.empty(N); uc_k = np.empty(N)
    saturated = np.zeros(N, dtype=bool)

    u_eff = 0.0  # plant input currently applied (after delay); system at rest for t < 0
    y_init = float(C1 @ x) + D1 * u_eff + d_out_sig(0.0)
    ctrl.reset(ControllerInit(Ts=Ts, r_init=ref(-Ts), y_init=y_init,
                              u_min=sat.u_min if sat.enabled else None,
                              u_max=sat.u_max if sat.enabled else None))

    diverged = False
    with np.errstate(over="ignore", invalid="ignore"):
        for k in range(N):
            tk = t_k[k]
            y_true = float(C1 @ x) + D1 * u_eff + d_out_sig(tk)
            y_meas = y_true + (rng.normal(0.0, noise_std) if noise_std > 0 else 0.0)
            rk = ref(tk)
            u_cmd = float(ctrl.compute(ControllerContext(k=k, t=tk, r=rk, y=y_meas, x=x.copy(), Ts=Ts)))
            u_sat = float(np.clip(u_cmd, u_lo, u_hi)) if math.isfinite(u_cmd) else u_cmd
            ctrl.commit(u_sat)
            r_k[k], ym_k[k], u_k[k], uc_k[k] = rk, y_meas, u_sat, u_cmd
            saturated[k] = u_sat != u_cmd

            base = k * n_sub
            for j in range(n_sub):
                t = tk + j * h
                din = d_in_sig(t)
                u_in = u_sat + din
                if delay_steps:
                    buf.append(u_in)
                    u_eff = buf.popleft()
                else:
                    u_eff = u_in
                dout = d_out_sig(t)
                i = base + j
                y_f[i] = float(C1 @ x) + D1 * u_eff + dout
                r_f[i], u_f[i], uc_f[i], di_f[i], do_f[i] = ref(t), u_sat, u_cmd, din, dout
                x = Phi @ x + Gam[:, 0] * u_eff
            if not np.all(np.isfinite(x)) or np.max(np.abs(x)) > 1e150:
                diverged = True
                # Fill the remainder with NaN; the run is meaningless from here on.
                y_f[base + n_sub:] = np.nan
                for arr in (r_f, u_f, uc_f, di_f, do_f):
                    arr[base + n_sub:] = np.nan
                r_k[k + 1:] = ym_k[k + 1:] = u_k[k + 1:] = uc_k[k + 1:] = np.nan
                break

    if not diverged:
        tN = N * Ts
        dout = d_out_sig(tN)
        y_f[-1] = float(C1 @ x) + D1 * u_eff + dout
        r_f[-1], u_f[-1], uc_f[-1], di_f[-1], do_f[-1] = ref(tN), u_f[-2], uc_f[-2], d_in_sig(tN), dout
    else:
        warnings.append("A simulação divergiu (sistema em malha fechada instável). Resultados truncados.")

    e_f = r_f - y_f

    # ----------------------------------------------------------- metrics
    valid = np.isfinite(y_f)
    metrics: dict[str, Any] = {}
    is_step = req.reference.type == "step"
    t_step = req.reference.time if is_step else 0.0
    if not diverged:
        if is_step:
            # Step indices characterise the *tracking* response: if a disturbance
            # starts after the step, evaluate them only up to that instant.
            starts = [d.time for d in req.disturbances if d.enabled and d.time > t_step + Ts]
            t_end = min(starts) if starts else N * Ts
            win = t_f <= t_end + 1e-12
            metrics.update(step_metrics(t_f[win], y_f[win], ref(tf), t_step, s.settling_band))
            metrics["step_window_end"] = float(t_end)
            if starts:
                warnings.append(
                    f"Índices da resposta ao degrau calculados em [{t_step:g}, {t_end:g}) s, antes da "
                    "primeira perturbação. IAE/ISE/ITAE usam todo o horizonte."
                )
            if not metrics.get("settled"):
                warnings.append(
                    "A saída não atingiu regime permanente na janela de avaliação: tempo de acomodação "
                    "não calculado. Aumente o tempo de simulação."
                    + (" (ou adie a perturbação)" if starts else "")
                )
            metrics["final_error"] = float(e_f[-1])
        else:
            metrics["steady_state_error"] = float(e_f[-1])
            metrics["final_value"] = float(y_f[-1])
        metrics.update(integral_metrics(t_f[valid], e_f[valid], t_step))
        metrics.update(control_metrics(t_f, u_f, u_k, saturated))
    metrics["stable_run"] = not diverged

    meta = {
        "n_samples": N,
        "n_substeps": n_sub,
        "h": h,
        "Ts": Ts,
        "t_final": N * Ts,
        "delay_effective": delay_eff,
        "plant_order": int(A.shape[0]),
        "integration": "ZOH exato (exponencial de matriz)",
        "metrics_window_start": t_step,
        "settling_band": s.settling_band,
        "reference_type": req.reference.type,
    }
    return SimulationResult(
        t=t_f, r=r_f, y=y_f, e=e_f, u=u_f, u_cmd=uc_f, d_in=di_f, d_out=do_f,
        t_k=t_k, r_k=r_k, y_meas_k=ym_k, u_k=u_k, u_cmd_k=uc_k,
        metrics=metrics, meta=meta, warnings=warnings,
    )


def result_to_json(res: SimulationResult, max_points: int) -> dict[str, Any]:
    """Serialise; the fine grid is decimated (stride) for plotting only.

    Metrics are always computed on the full-resolution data. Decimation keeps
    the global extrema of y so the plotted peak matches the overshoot metric.
    """
    M = res.t.size

    def pick(n: int, limit: int) -> np.ndarray:
        if n <= limit:
            return np.arange(n)
        stride = math.ceil(n / limit)
        return np.arange(0, n, stride)

    idx = pick(M, max_points)
    if M > max_points:
        y = res.y
        finite = np.isfinite(y)
        if finite.any():
            extra = [int(np.nanargmax(y)), int(np.nanargmin(y)), M - 1]
            idx = np.unique(np.concatenate([idx, extra]))
    kidx = pick(res.t_k.size, max_points)

    fine = {k: _sanitize(getattr(res, k)[idx]) for k in ("t", "r", "y", "e", "u", "u_cmd", "d_in", "d_out")}
    samples = {
        "t": _sanitize(res.t_k[kidx]), "r": _sanitize(res.r_k[kidx]),
        "y_meas": _sanitize(res.y_meas_k[kidx]), "u": _sanitize(res.u_k[kidx]),
        "u_cmd": _sanitize(res.u_cmd_k[kidx]),
    }
    metrics = {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
               for k, v in res.metrics.items()}
    meta = dict(res.meta, plotted_points=int(idx.size), decimated=bool(M > max_points))
    return {"signals": fine, "samples": samples, "metrics": metrics, "meta": meta,
            "warnings": res.warnings}


def result_to_csv(res: SimulationResult) -> str:
    import io

    buf = io.StringIO()
    buf.write("# ControlLab - dados em resolucao completa (grade de integracao)\n")
    buf.write(f"# Ts={res.meta['Ts']}, h={res.meta['h']}, amostras={res.meta['n_samples']}\n")
    buf.write("t,r,y,e,u,u_cmd,d_in,d_out\n")
    data = np.column_stack([res.t, res.r, res.y, res.e, res.u, res.u_cmd, res.d_in, res.d_out])
    np.savetxt(buf, data, delimiter=",", fmt="%.10g")
    return buf.getvalue()
