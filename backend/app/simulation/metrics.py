"""Performance indices.

Step-response indices follow the usual textbook / MATLAB ``stepinfo``
conventions, measured relative to the *actual* final value of the output:

    Δ          = y_ss − y(t_step)
    overshoot  = (y_peak − y_ss)/Δ · 100 %          (0 when no overshoot)
    rise time  = t(90 %Δ) − t(10 %Δ)                 (linear interpolation)
    settling   = last instant |y − y_ss| > band·|Δ|, measured from t_step
    e_ss       = r_final − y_ss

y_ss is the last sample of the simulation. If the output is still moving
(variation in the last 10 % of the horizon larger than the band) the response
is flagged as *not settled* and settling-related indices are reported as None,
instead of returning misleading numbers.

Integral indices use the trapezoidal rule on the fine integration grid. For a
step reference they are evaluated on [t_step, t_final] with time measured from
the step instant (ITAE = ∫ (t − t_step)|e| dt), which matches their textbook
definition for a step applied at t = 0. For other references the full horizon
is used.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    return float(np.trapezoid(y, x)) if x.size > 1 else 0.0


def _crossing(t: np.ndarray, y: np.ndarray, level: float, rising: bool) -> float | None:
    s = (y - level) if rising else (level - y)
    idx = np.flatnonzero(s >= 0)
    if idx.size == 0:
        return None
    i = idx[0]
    if i == 0:
        return float(t[0])
    # linear interpolation between i-1 and i
    s0, s1 = s[i - 1], s[i]
    frac = -s0 / (s1 - s0) if s1 != s0 else 0.0
    return float(t[i - 1] + frac * (t[i] - t[i - 1]))


def step_metrics(t: np.ndarray, y: np.ndarray, r_final: float, t_step: float,
                 band: float) -> dict[str, Any]:
    mask = t >= t_step - 1e-12
    tt, yy = t[mask] - t_step, y[mask]
    out: dict[str, Any] = {
        "overshoot_pct": None, "peak_value": None, "peak_time": None,
        "rise_time": None, "settling_time": None, "steady_state_error": None,
        "final_value": None, "settled": False,
    }
    if tt.size < 3:
        return out
    y0, y_ss = float(yy[0]), float(yy[-1])
    out["final_value"] = y_ss
    out["steady_state_error"] = float(r_final - y_ss)
    delta = y_ss - y0
    scale = max(abs(r_final), abs(y_ss), abs(y0), 1e-12)
    if not np.isfinite(y_ss) or abs(delta) < 1e-9 * scale:
        return out

    # Settled? Compare the variation in the last 10 % of the window with the band.
    tail = tt >= 0.9 * tt[-1]
    tol = band * abs(delta)
    out["settled"] = bool(np.max(np.abs(yy[tail] - y_ss)) <= tol)

    sgn = np.sign(delta)
    k_peak = int(np.argmax(sgn * yy))
    out["peak_value"] = float(yy[k_peak])
    out["peak_time"] = float(tt[k_peak])
    out["overshoot_pct"] = float(max(0.0, sgn * (yy[k_peak] - y_ss) / abs(delta) * 100.0))
    if out["overshoot_pct"] == 0.0:
        # monotone response: the "peak" is just the end of the window, not a feature
        out["peak_value"] = out["peak_time"] = None

    rising = delta > 0
    t10 = _crossing(tt, yy, y0 + 0.1 * delta, rising)
    t90 = _crossing(tt, yy, y0 + 0.9 * delta, rising)
    if t10 is not None and t90 is not None:
        out["rise_time"] = t90 - t10

    if out["settled"]:
        outside = np.flatnonzero(np.abs(yy - y_ss) > tol)
        out["settling_time"] = float(tt[outside[-1] + 1]) if outside.size else 0.0
    return out


def integral_metrics(t: np.ndarray, e: np.ndarray, t0: float) -> dict[str, float]:
    mask = t >= t0 - 1e-12
    tt, ee = t[mask], e[mask]
    tau = tt - t0
    return {
        "IAE": _trapz(np.abs(ee), tt),
        "ISE": _trapz(ee**2, tt),
        "ITAE": _trapz(tau * np.abs(ee), tt),
        "ITSE": _trapz(tau * ee**2, tt),
    }


def control_metrics(t: np.ndarray, u: np.ndarray, u_samples: np.ndarray,
                    saturated: np.ndarray) -> dict[str, float]:
    return {
        "u_max_abs": float(np.max(np.abs(u))) if u.size else 0.0,
        "control_energy": _trapz(u**2, t),          # ∫ u² dt
        "total_variation": float(np.sum(np.abs(np.diff(u_samples)))),  # Σ|Δu_k|
        "saturation_pct": float(100.0 * np.mean(saturated)) if saturated.size else 0.0,
    }
