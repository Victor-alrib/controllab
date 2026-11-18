"""Reference and disturbance signal generators (pure functions of time)."""
from __future__ import annotations

from typing import Callable

import numpy as np

from app.schemas import DisturbanceConfig, ReferenceConfig

Signal = Callable[[float], float]

# Tolerance so that events placed exactly on the time grid (e.g. t0 = 0.3 with
# Ts = 0.1) are not missed because of floating-point round-off in k·Ts.
_EPS = 1e-9


def _after(t: float, t0: float) -> bool:
    return t + _EPS * max(1.0, abs(t0)) >= t0


def reference_signal(cfg: ReferenceConfig) -> Signal:
    r0, A, t0 = cfg.initial, cfg.amplitude, cfg.time
    if cfg.type == "constant":
        return lambda t: A
    if cfg.type == "step":
        return lambda t: A if _after(t, t0) else r0
    if cfg.type == "ramp":
        return lambda t: r0 + cfg.slope * (t - t0) if _after(t, t0) else r0
    w = 2 * np.pi * cfg.frequency
    if cfg.type == "sine":
        return lambda t: r0 + A * np.sin(w * (t - t0)) if _after(t, t0) else r0
    if cfg.type == "square":
        # +A during the first half period, −A during the second (zero mean around r0)
        return lambda t: (r0 + A * (1.0 if ((t - t0) * cfg.frequency) % 1.0 < 0.5 else -1.0)
                          if _after(t, t0) else r0)
    raise ValueError(cfg.type)


def disturbance_signal(cfg: DisturbanceConfig) -> Signal:
    A, t0 = cfg.amplitude, cfg.time
    if not cfg.enabled:
        return lambda t: 0.0
    if cfg.shape == "step":
        return lambda t: A if _after(t, t0) else 0.0
    if cfg.shape == "pulse":
        return lambda t: A if _after(t, t0) and not _after(t, t0 + cfg.duration) else 0.0
    w = 2 * np.pi * cfg.frequency
    return lambda t: A * np.sin(w * (t - t0)) if _after(t, t0) else 0.0


def sum_signals(signals: list[Signal]) -> Signal:
    if not signals:
        return lambda t: 0.0
    return lambda t: float(sum(s(t) for s in signals))
