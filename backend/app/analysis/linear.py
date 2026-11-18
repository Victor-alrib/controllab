"""Linear (small-signal) analysis of the configured loop.

Everything here ignores saturation, noise and disturbances (they do not change
poles or margins of an LTI loop). Two views are provided:

* Continuous-time: G(s)·e^{-θs} with the continuous PID C(s). Frequency
  responses and stability margins use the *exact* delay e^{-jωθ}; poles of a
  delayed loop are infinite in number, so the closed-loop poles reported use a
  Padé approximation (flagged in the response).
* Discrete-time (what is actually simulated): G(z) = ZOH{G(s)}, the delay as
  z^{-d} when θ is a multiple of Ts, and the exact z-domain transfer function of
  the implemented PID difference equations. Its closed-loop poles determine the
  stability of the simulated (unsaturated) loop exactly.
"""
from __future__ import annotations

import math
from typing import Any

import control
import numpy as np

from app.controllers.registry import build_controller
from app.plants.registry import build_plant
from app.schemas import SimulationRequest

PADE_ORDER = 6


def _cplx(values) -> list[list[float]]:
    return [[float(np.real(v)), float(np.imag(v))] for v in np.atleast_1d(values)]


def _poly(tf: control.TransferFunction) -> tuple[np.ndarray, np.ndarray]:
    num, den = control.tfdata(tf)
    return np.atleast_1d(np.squeeze(num[0][0])), np.atleast_1d(np.squeeze(den[0][0]))


def _char_poly(L_num, L_den) -> np.ndarray:
    """Characteristic polynomial of 1 + L = 0 without pole/zero cancellation."""
    return np.polyadd(L_den, L_num)


def _finite(x: float) -> float | None:
    return float(x) if x is not None and math.isfinite(x) else None


def _pole_info(poles: np.ndarray, Ts: float | None = None) -> list[dict[str, float]]:
    out = []
    for p in poles:
        entry = {"re": float(np.real(p)), "im": float(np.imag(p)), "mag": float(abs(p)),
                 "wn": None, "zeta": None}
        if Ts and abs(p) < 1e-12:
            out.append(entry)  # z = 0 (dead-beat / pure delay): no s-plane equivalent
            continue
        s = np.log(complex(p)) / Ts if Ts else p  # map z-poles to the equivalent s-plane
        wn = float(abs(s))
        entry["wn"] = wn
        entry["zeta"] = float(-np.real(s) / wn) if wn > 1e-12 else 1.0
        out.append(entry)
    return out


def analyze(req: SimulationRequest, n_freq: int = 400) -> dict[str, Any]:
    plant = build_plant(req.plant.type, req.plant.params)
    ctrl = build_controller(req.controller.type, req.controller.params)
    Ts = req.settings.Ts
    theta = plant.delay
    G = plant.transfer_function()
    g_num, g_den = _poly(G)
    gp = control.poles(G)
    gz = control.zeros(G)
    try:
        dc = float(np.real(control.dcgain(G)))
        dc = _finite(dc)
    except Exception:  # integrator → infinite DC gain
        dc = None

    out: dict[str, Any] = {
        "plant": {
            "num": g_num.tolist(), "den": g_den.tolist(),
            "poles": _pole_info(gp), "zeros": _cplx(gz),
            "dc_gain": dc, "delay": theta,
            "stable": bool(np.all(np.real(gp) < 0)),
        },
        "notes": [],
    }

    # ---- open-loop plant step response (exact: delay is a pure time shift)
    T_end = req.settings.t_final
    T = np.linspace(0.0, T_end, 800)
    resp = control.step_response(G, T)
    y = np.asarray(resp.outputs).reshape(-1)
    y_shift = np.interp(T - theta, T, y, left=0.0)
    out["plant_step"] = {"t": T.tolist(), "y": [_finite(v) for v in y_shift]}

    tfs_c = ctrl.transfer_functions("continuous")
    tfs_d = ctrl.transfer_functions("discrete", Ts)
    if tfs_c is None or tfs_d is None:
        out["closed_loop"] = None
        out["notes"].append("Controlador não linear: análise linear não se aplica.")
        return out

    Cr, Cy = tfs_c
    c_num, c_den = _poly(Cy)
    out["controller"] = {
        "Cy_num": c_num.tolist(), "Cy_den": c_den.tolist(),
        "Cr_num": _poly(Cr)[0].tolist(), "Cr_den": _poly(Cr)[1].tolist(),
    }
    feedback = req.controller.type != "open_loop"

    # ---- frequency response of L(jω) = Cy(jω)G(jω)e^{-jωθ} (exact delay)
    if feedback:
        poles_all = np.concatenate([gp, control.poles(Cy)])
        mags = np.abs(poles_all[np.abs(poles_all) > 1e-9])
        w_lo = 10 ** (np.floor(np.log10(mags.min())) - 2) if mags.size else 1e-3
        w_hi = 10 ** (np.ceil(np.log10(mags.max())) + 2) if mags.size else 1e3
        w = np.logspace(np.log10(w_lo), np.log10(max(w_hi, w_lo * 100)), n_freq)
        L = Cy * G
        Ljw = np.asarray(L(1j * w)).reshape(-1) * np.exp(-1j * w * theta)
        mag = np.abs(Ljw)
        phase = np.unwrap(np.angle(Ljw))
        gm, pm, wcg, wcp = _margins(mag, phase, w)
        out["open_loop_freq"] = {
            "w": w.tolist(),
            "mag_db": [_finite(20 * np.log10(m)) if m > 0 else None for m in mag],
            "phase_deg": np.degrees(phase).tolist(),
        }
        out["margins"] = {"gain_margin_db": gm, "phase_margin_deg": pm,
                          "w_phase_crossover": wcg, "w_gain_crossover": wcp}

    # ---- continuous closed-loop poles (Padé for delay)
    G_c = G
    if theta > 0:
        pn, pd = control.pade(theta, PADE_ORDER)
        G_c = G * control.tf(pn, pd)
        out["notes"].append(
            f"Polos contínuos com atraso calculados via aproximação de Padé de ordem {PADE_ORDER}."
        )
    if feedback:
        Ln, Ld = _poly(Cy * G_c)
        cl_c = np.roots(_char_poly(Ln, Ld))
    else:
        cl_c = control.poles(G_c)
    # ---- discrete closed-loop poles (exact for the simulated difference equations)
    Gd = control.c2d(G, Ts, method="zoh")
    d = theta / Ts
    if theta > 0:
        if abs(d - round(d)) < 1e-9:
            Gd = Gd * control.tf([1.0], [1.0] + [0.0] * int(round(d)), Ts)
        else:
            pn, pd = control.pade(theta, PADE_ORDER)
            Gd = control.c2d(G * control.tf(pn, pd), Ts, method="zoh")
            out["notes"].append(
                "Atraso não múltiplo de Ts: polos discretos usam Padé (a simulação usa o atraso "
                "arredondado ao passo de integração)."
            )
    Crd, Cyd = tfs_d
    if feedback:
        Ln, Ld = _poly(Cyd * Gd)
        cl_d = np.roots(_char_poly(Ln, Ld))
    else:
        cl_d = control.poles(Gd)
    out["closed_loop"] = {
        "continuous_poles": _pole_info(cl_c),
        "continuous_stable": bool(np.all(np.real(cl_c) < 0)),
        "discrete_poles": _pole_info(cl_d, Ts),
        "discrete_stable": bool(np.all(np.abs(cl_d) < 1.0)),
        "spectral_radius": float(np.max(np.abs(cl_d))) if cl_d.size else 0.0,
    }
    return out


def _margins(mag: np.ndarray, phase: np.ndarray, w: np.ndarray):
    """Gain/phase margins from sampled frequency response (linear interpolation).

    Returns the smallest-magnitude margins over all crossovers.
    """
    gm = pm = wcg = wcp = None
    # gain crossover: |L| = 1
    lm = np.log10(np.maximum(mag, 1e-300))
    idx = np.flatnonzero(np.sign(lm[:-1]) * np.sign(lm[1:]) < 0)
    best = None
    for i in idx:
        f = lm[i] / (lm[i] - lm[i + 1])
        wc = w[i] * (w[i + 1] / w[i]) ** f
        ph = phase[i] + f * (phase[i + 1] - phase[i])
        margin = (np.degrees(ph) + 180.0) % 360.0
        margin = margin - 360.0 if margin > 180.0 else margin
        if best is None or abs(margin) < abs(best):
            best, wcp = margin, wc
    pm = _finite(best) if best is not None else None
    wcp = _finite(wcp) if wcp is not None else None
    # phase crossover: phase = -180° (mod 360)
    ph_shift = (np.degrees(phase) + 180.0) / 360.0
    k = np.floor(ph_shift)
    idx = np.flatnonzero(np.diff(k) != 0)
    bestg = None
    for i in idx:
        target = max(k[i], k[i + 1]) * 360.0 - 180.0
        p0, p1 = np.degrees(phase[i]), np.degrees(phase[i + 1])
        f = (target - p0) / (p1 - p0) if p1 != p0 else 0.0
        m = 10 ** (lm[i] + f * (lm[i + 1] - lm[i]))
        g = -20 * np.log10(m)
        if bestg is None or abs(g) < abs(bestg):
            bestg, wcg = g, w[i] * (w[i + 1] / w[i]) ** f
    gm = _finite(bestg) if bestg is not None else None
    wcg = _finite(wcg) if wcg is not None else None
    return gm, pm, wcg, wcp
