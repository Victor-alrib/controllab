"""Mathematical fidelity tests: simulation vs. closed-form / python-control results."""
from __future__ import annotations

import control
import numpy as np
import pytest

from app.analysis.linear import analyze
from app.controllers.registry import build_controller
from app.core.params import ParamError
from app.schemas import SimulationRequest
from app.simulation.engine import simulate
from app.simulation.metrics import step_metrics


def req(plant, ctrl, **kw) -> SimulationRequest:
    base = {
        "plant": plant,
        "controller": ctrl,
        "reference": kw.pop("reference", {"type": "step", "amplitude": 1.0, "time": 0.0}),
        "settings": kw.pop("settings", {"t_final": 10.0, "Ts": 0.01}),
    }
    base.update(kw)
    return SimulationRequest.model_validate(base)


OL1 = {"type": "open_loop", "params": {"Kff": 1.0}}


def test_first_order_open_loop_exact():
    K, tau = 2.0, 0.7
    res = simulate(req({"type": "first_order", "params": {"K": K, "tau": tau}}, OL1))
    y_exact = K * (1 - np.exp(-res.t / tau))
    assert np.max(np.abs(res.y - y_exact)) < 1e-10


def test_first_order_initial_condition_free_response():
    res = simulate(req({"type": "first_order", "params": {"K": 1, "tau": 2, "y0": 3}},
                       {"type": "open_loop", "params": {"Kff": 0}}))
    assert np.max(np.abs(res.y - 3 * np.exp(-res.t / 2))) < 1e-10


@pytest.mark.parametrize("zeta", [0.1, 0.5, 0.9])
def test_second_order_step_and_overshoot(zeta):
    wn, K = 3.0, 1.5
    res = simulate(req({"type": "second_order", "params": {"K": K, "wn": wn, "zeta": zeta}}, OL1,
                       settings={"t_final": 60.0, "Ts": 0.001}))
    wd = wn * np.sqrt(1 - zeta**2)
    phi = np.arccos(zeta)
    y_exact = K * (1 - np.exp(-zeta * wn * res.t) / np.sqrt(1 - zeta**2) * np.sin(wd * res.t + phi))
    assert np.max(np.abs(res.y - y_exact)) < 1e-9
    Mp = np.exp(-zeta * np.pi / np.sqrt(1 - zeta**2)) * 100
    assert res.metrics["overshoot_pct"] == pytest.approx(Mp, rel=1e-4)
    assert res.metrics["peak_time"] == pytest.approx(np.pi / wd, abs=2e-3)


def test_second_order_initial_conditions():
    wn, z = 2.0, 0.0
    res = simulate(req({"type": "second_order", "params": {"wn": wn, "zeta": z, "y0": 1, "dy0": 2}},
                       {"type": "open_loop", "params": {"Kff": 0}}))
    exact = np.cos(wn * res.t) + 2 / wn * np.sin(wn * res.t)
    assert np.max(np.abs(res.y - exact)) < 1e-9


def test_tf_and_ss_agree_with_python_control():
    num, den = [1.0, 2.0], [1.0, 3.0, 5.0, 1.0]
    r1 = simulate(req({"type": "transfer_function", "params": {"num": num, "den": den}}, OL1))
    T = r1.t
    y_ref = np.asarray(control.step_response(control.tf(num, den), T).outputs).reshape(-1)
    assert np.max(np.abs(r1.y - y_ref)) < 1e-8
    A = [[0, 1], [-2, -3]]
    r2 = simulate(req({"type": "state_space", "params": {"A": A, "B": [[0], [1]], "C": [[1, 0]],
                                                         "D": [[0]], "x0": [0, 0]}}, OL1))
    y2 = np.asarray(control.step_response(control.ss(A, [[0], [1]], [[1, 0]], 0), r2.t).outputs).reshape(-1)
    assert np.max(np.abs(r2.y - y2)) < 1e-10


def test_delay_is_exact_shift():
    res = simulate(req({"type": "first_order", "params": {"K": 1, "tau": 1, "delay": 0.5}}, OL1))
    exact = np.where(res.t >= 0.5, 1 - np.exp(-(res.t - 0.5)), 0.0)
    assert np.max(np.abs(res.y - exact)) < 1e-9


def test_p_control_steady_state_error():
    K, Kp = 2.0, 3.0
    res = simulate(req({"type": "first_order", "params": {"K": K, "tau": 1}},
                       {"type": "p", "params": {"Kp": Kp}}, settings={"t_final": 20, "Ts": 0.01}))
    assert res.metrics["steady_state_error"] == pytest.approx(1 / (1 + K * Kp), abs=1e-6)


def test_pi_zero_steady_state_error_with_input_disturbance():
    res = simulate(req({"type": "second_order", "params": {"wn": 2, "zeta": 0.7}},
                       {"type": "pi", "params": {"Kp": 1.0, "Ki": 1.0}},
                       settings={"t_final": 40, "Ts": 0.01},
                       disturbances=[{"target": "input", "shape": "step", "amplitude": 0.5, "time": 15}]))
    assert abs(res.e[-1]) < 1e-5


@pytest.mark.parametrize("method", ["forward", "backward", "tustin"])
def test_simulated_loop_matches_exact_discrete_closed_loop(method):
    """Unsaturated simulation at the sampling instants must equal the linear
    discrete closed loop built from ZOH{G} and the PID z-transfer functions."""
    Ts = 0.05
    cfg = req({"type": "second_order", "params": {"K": 1, "wn": 2, "zeta": 0.4}},
              {"type": "pid", "params": {"Kp": 2, "Ki": 1.5, "Kd": 0.4, "Tf": 0.05, "b": 0.7, "c": 0.0,
                                         "integration": method}},
              settings={"t_final": 10, "Ts": Ts})
    res = simulate(cfg)
    ctrl = build_controller("pid", cfg.controller.params)
    Cr, Cy = ctrl.transfer_functions("discrete", Ts)
    G = control.tf([4.0], [1, 1.6, 4])
    Gd = control.c2d(G, Ts, "zoh")
    # state-space interconnection: no pole/zero cancellation in the reference model
    Tcl = control.series(control.ss(Cr), control.feedback(control.ss(Gd), control.ss(Cy)))
    N = res.t_k.size
    yd = np.asarray(control.step_response(Tcl, np.arange(N) * Ts).outputs).reshape(-1)
    y_sim = res.y[:: res.meta["n_substeps"]][:N]
    assert np.max(np.abs(y_sim - yd)) < 1e-10


def test_analysis_poles_consistent_with_stability():
    cfg = req({"type": "second_order", "params": {"wn": 1, "zeta": 0.2}},
              {"type": "pid", "params": {"Kp": 50, "Ki": 0, "Kd": 0, "Tf": 0}},
              settings={"t_final": 5, "Ts": 0.2})
    ana = analyze(cfg)
    res = simulate(cfg)
    assert ana["closed_loop"]["continuous_stable"] is True        # 2nd order + P is always stable
    assert ana["closed_loop"]["discrete_stable"] is False         # but sampling destabilises it
    assert not res.metrics["stable_run"] or abs(res.y[-1]) > 10


def test_margins_first_order_with_delay():
    # L = Kp·e^{-θs}/(s+1). Exact phase margin at ωc = sqrt(Kp²-1): 180 - atan(ωc)·180/π - ωc·θ·180/π
    Kp, th = 4.0, 0.2
    ana = analyze(req({"type": "first_order", "params": {"K": 1, "tau": 1, "delay": th}},
                      {"type": "p", "params": {"Kp": Kp}}))
    wc = np.sqrt(Kp**2 - 1)
    pm = 180 - np.degrees(np.arctan(wc)) - np.degrees(wc * th)
    assert ana["margins"]["phase_margin_deg"] == pytest.approx(pm, abs=0.05)


def test_saturation_and_antiwindup_reduce_overshoot():
    base = dict(plant={"type": "first_order", "params": {"K": 1, "tau": 1}},
                settings={"t_final": 30, "Ts": 0.01}, saturation={"enabled": True, "u_min": -1.2, "u_max": 1.2})
    no_aw = simulate(req(ctrl={"type": "pi", "params": {"Kp": 2, "Ki": 3, "anti_windup": "none"}}, **base))
    bc = simulate(req(ctrl={"type": "pi", "params": {"Kp": 2, "Ki": 3, "anti_windup": "back_calculation", "Kt": 2}}, **base))
    cl = simulate(req(ctrl={"type": "pi", "params": {"Kp": 2, "Ki": 3, "anti_windup": "clamping"}}, **base))
    assert np.max(np.abs(no_aw.u)) <= 1.2 + 1e-12
    assert bc.metrics["overshoot_pct"] < no_aw.metrics["overshoot_pct"]
    assert cl.metrics["overshoot_pct"] < no_aw.metrics["overshoot_pct"]


def test_integral_metrics_first_order():
    # e(t) = exp(-t/τ) for K=1 open loop → IAE = τ, ISE = τ/2, ITAE = τ²
    tau = 0.5
    res = simulate(req({"type": "first_order", "params": {"K": 1, "tau": tau}}, OL1,
                       settings={"t_final": 20, "Ts": 0.001}))
    assert res.metrics["IAE"] == pytest.approx(tau, rel=1e-4)
    assert res.metrics["ISE"] == pytest.approx(tau / 2, rel=1e-4)
    assert res.metrics["ITAE"] == pytest.approx(tau**2, rel=1e-4)


def test_first_order_rise_and_settling():
    tau = 1.0
    res = simulate(req({"type": "first_order", "params": {"K": 1, "tau": tau}}, OL1,
                       settings={"t_final": 30, "Ts": 0.001}))
    assert res.metrics["rise_time"] == pytest.approx(tau * np.log(9), rel=1e-4)
    # y_ss is the last sample (≈1 − e^{-30}); 2 % band → t_s = τ ln 50
    assert res.metrics["settling_time"] == pytest.approx(tau * np.log(50), abs=2e-3)


def test_not_settled_is_flagged():
    t = np.linspace(0, 1, 1000)
    m = step_metrics(t, 1 - np.exp(-t / 5), 1.0, 0.0, 0.02)
    assert m["settled"] is False and m["settling_time"] is None


def test_invalid_inputs():
    with pytest.raises(ParamError):
        simulate(req({"type": "first_order", "params": {"tau": 0}}, OL1))
    with pytest.raises(ParamError):
        simulate(req({"type": "transfer_function", "params": {"num": [1, 0, 0], "den": [1, 1]}}, OL1))
    with pytest.raises(ParamError):
        simulate(req({"type": "first_order"}, {"type": "lqr"}))


def test_step_metrics_window_excludes_later_disturbance():
    cfg = dict(settings={"t_final": 20, "Ts": 0.001},
               disturbances=[{"target": "input", "shape": "step", "amplitude": 0.5, "time": 15}])
    res = simulate(req({"type": "first_order", "params": {"K": 1, "tau": 1}}, OL1, **cfg))
    assert res.metrics["step_window_end"] == 15
    assert res.metrics["overshoot_pct"] == 0.0
    assert res.metrics["rise_time"] == pytest.approx(np.log(9), rel=1e-3)
