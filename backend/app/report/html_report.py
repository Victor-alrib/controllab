"""Self-contained HTML report (figures rendered with Matplotlib from the
simulation data, embedded as base64 PNG). Print to PDF from the browser."""
from __future__ import annotations

import base64
import html
import io
from datetime import datetime
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from app.analysis.linear import analyze  # noqa: E402
from app.controllers.registry import CONTROLLERS  # noqa: E402
from app.plants.registry import PLANTS  # noqa: E402
from app.schemas import ReportRequest  # noqa: E402
from app.simulation.engine import simulate  # noqa: E402

COLORS = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#db2777", "#0891b2",
          "#65a30d", "#9333ea", "#475569"]

METRIC_ROWS = [
    ("overshoot_pct", "Overshoot", "%", 2),
    ("rise_time", "Tempo de subida (10–90%)", "s", 4),
    ("settling_time", "Tempo de acomodação", "s", 4),
    ("peak_time", "Tempo de pico", "s", 4),
    ("steady_state_error", "Erro em regime", "", 5),
    ("IAE", "IAE", "", 5),
    ("ISE", "ISE", "", 5),
    ("ITAE", "ITAE", "", 5),
    ("u_max_abs", "max |u|", "", 4),
    ("control_energy", "∫u² dt", "", 4),
    ("saturation_pct", "Tempo saturado", "%", 1),
]


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def _fmt(v: Any, nd: int) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, (int, float)):
        return f"{v:.{nd}g}" if abs(v) >= 1e4 or (abs(v) < 1e-3 and v != 0) else f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return html.escape(str(v))


def _params_table(params: dict[str, Any], specs) -> str:
    labels = {s.key: (s.label, s.unit) for s in specs}
    rows = []
    for k, v in params.items():
        lab, unit = labels.get(k, (k, ""))
        rows.append(f"<tr><td>{html.escape(lab)}</td><td>{html.escape(str(v))} {unit}</td></tr>")
    return "<table class='kv'>" + "".join(rows) + "</table>"


def build_report(req: ReportRequest) -> str:
    sims = []
    for run in req.runs:
        res = simulate(run.config)
        try:
            ana = analyze(run.config)
        except Exception as exc:  # analysis is auxiliary; never block the report
            ana = {"error": str(exc)}
        sims.append((run, res, ana))

    plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3})
    fig, axes = plt.subplots(3, 1, figsize=(8.5, 8.5), sharex=True)
    for i, (run, res, _) in enumerate(sims):
        c = COLORS[i % len(COLORS)]
        axes[0].plot(res.t, res.y, color=c, lw=1.4, label=f"y — {run.label}")
        axes[0].plot(res.t, res.r, color=c, lw=0.9, ls="--", alpha=0.7)
        axes[1].plot(res.t, res.e, color=c, lw=1.2, label=run.label)
        axes[2].plot(res.t, res.u, color=c, lw=1.2, label=run.label, drawstyle="steps-post")
    axes[0].set_ylabel("saída y / referência r (--)")
    axes[1].set_ylabel("erro e = r − y")
    axes[2].set_ylabel("controle u (aplicado)")
    axes[2].set_xlabel("tempo [s]")
    axes[0].legend(loc="best", fontsize=8)
    fig_main = _fig_to_b64(fig)

    head = "".join(f"<th style='color:{COLORS[i % len(COLORS)]}'>{html.escape(r.label)}</th>"
                   for i, (r, _, _) in enumerate(sims))
    body = []
    for key, label, unit, nd in METRIC_ROWS:
        cells = "".join(f"<td>{_fmt(res.metrics.get(key), nd)}</td>" for _, res, _ in sims)
        body.append(f"<tr><td>{label}{f' [{unit}]' if unit else ''}</td>{cells}</tr>")
    metrics_table = f"<table class='grid'><tr><th>Indicador</th>{head}</tr>{''.join(body)}</table>"

    sections = []
    for i, (run, res, ana) in enumerate(sims):
        cfg = run.config
        pcls, ccls = PLANTS[cfg.plant.type], CONTROLLERS[cfg.controller.type]
        from app.core.params import coerce_params

        pparams = coerce_params(pcls.param_specs, cfg.plant.params)
        cparams = coerce_params(ccls.param_specs, cfg.controller.params)
        pparams = {k: (np.asarray(v).tolist() if isinstance(v, np.ndarray) else v) for k, v in pparams.items()}
        cl = ana.get("closed_loop") if isinstance(ana, dict) else None
        poles = ""
        if cl:
            pz = ", ".join(
                f"{p['re']:.4g}{'+' if p['im'] >= 0 else '−'}{abs(p['im']):.4g}j" for p in cl["discrete_poles"]
            )
            poles = (f"<p><b>Polos de malha fechada (z, exatos para a simulação sem saturação):</b> {pz}"
                     f" — raio espectral {cl['spectral_radius']:.4f} "
                     f"({'estável' if cl['discrete_stable'] else 'INSTÁVEL'})</p>")
            m = ana.get("margins")
            if m:
                poles += (f"<p><b>Margens (tempo contínuo, atraso exato):</b> MG = {_fmt(m['gain_margin_db'], 4)} dB, "
                          f"MF = {_fmt(m['phase_margin_deg'], 4)}°</p>")
        warn = "".join(f"<li>{html.escape(w)}</li>" for w in res.warnings)
        sections.append(f"""
<section>
<h3 style='color:{COLORS[i % len(COLORS)]}'>{html.escape(run.label)}</h3>
<div class='cols'>
 <div><h4>Planta — {html.escape(pcls.name)}</h4>{_params_table(pparams, pcls.param_specs)}</div>
 <div><h4>Controlador — {html.escape(ccls.name)}</h4>{_params_table(cparams, ccls.param_specs)}</div>
 <div><h4>Simulação</h4><table class='kv'>
  <tr><td>Referência</td><td>{cfg.reference.type}, amplitude {cfg.reference.amplitude}, t₀ = {cfg.reference.time} s</td></tr>
  <tr><td>Tempo final / Ts</td><td>{res.meta['t_final']:g} s / {cfg.settings.Ts:g} s</td></tr>
  <tr><td>Passo de integração h</td><td>{res.meta['h']:.4g} s (ZOH exato)</td></tr>
  <tr><td>Saturação</td><td>{'[' + str(cfg.saturation.u_min) + ', ' + str(cfg.saturation.u_max) + ']' if cfg.saturation.enabled else 'desativada'}</td></tr>
  <tr><td>Perturbações</td><td>{len([d for d in cfg.disturbances if d.enabled])}</td></tr>
  <tr><td>Ruído de medição</td><td>{'σ = ' + str(cfg.noise.std) if cfg.noise.enabled else 'desativado'}</td></tr>
 </table></div>
</div>
{poles}
{f'<ul class="warn">{warn}</ul>' if warn else ''}
</section>""")

    notes = f"<p class='notes'>{html.escape(req.notes)}</p>" if req.notes else ""
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<title>{html.escape(req.title)}</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:960px;margin:24px auto;color:#111;padding:0 16px}}
h1{{margin-bottom:0}} .sub{{color:#555;margin-top:4px}}
table{{border-collapse:collapse;font-size:13px}} .grid td,.grid th{{border:1px solid #ccc;padding:4px 8px;text-align:right}}
.grid td:first-child{{text-align:left}} .kv td{{padding:2px 8px;border-bottom:1px solid #eee}}
.cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}} h4{{margin:6px 0}}
section{{border-top:1px solid #ddd;margin-top:16px}} .warn{{color:#a15c00;font-size:13px}}
img{{max-width:100%}} .foot{{color:#777;font-size:12px;margin-top:24px}}
@media print{{section{{break-inside:avoid}}}}
</style></head><body>
<h1>{html.escape(req.title)}</h1>
<p class="sub">{html.escape(req.author) + ' — ' if req.author else ''}{datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
{notes}
<h2>Respostas</h2><img src="data:image/png;base64,{fig_main}" alt="Respostas temporais">
<h2>Indicadores de desempenho</h2>{metrics_table}
<p class="foot">Índices de degrau relativos ao valor final da saída; faixa de acomodação de
{sims[0][0].config.settings.settling_band * 100:g}%. IAE/ISE/ITAE integrados (regra trapezoidal) a partir do instante do degrau.</p>
<h2>Configurações</h2>{''.join(sections)}
<p class="foot">Gerado pelo ControlLab. Integração da planta por discretização ZOH exata; controlador discreto com período Ts.</p>
</body></html>"""
