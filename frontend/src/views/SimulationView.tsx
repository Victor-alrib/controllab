import { useState } from "react";
import type { Data } from "plotly.js";
import type { Analysis, SimResult } from "../types";
import { C, Plot } from "../components/Plot";
import { Toggle } from "../components/Fields";

export function SimulationView({ result, analysis }: { result?: SimResult; analysis?: Analysis }) {
  const [showMeas, setShowMeas] = useState(false);
  const [showDist, setShowDist] = useState(true);
  if (!result) return <div className="empty big">Configure a planta e o controlador — a simulação é executada automaticamente.</div>;
  const s = result.signals;
  const hasSat = result.metrics.saturation_pct !== undefined && result.metrics.saturation_pct > 0;
  const hasDist = s.d_in.some((v) => v) || s.d_out.some((v) => v);

  const out: Data[] = [
    { x: s.t, y: s.r, name: "referência r", type: "scattergl", mode: "lines", line: { color: C.ref, dash: "dash", width: 1.4 } },
    ...(showMeas
      ? [{ x: result.samples.t, y: result.samples.y_meas, name: "medição y_k", type: "scattergl", mode: "markers", marker: { color: C.meas, size: 3 } } as Data]
      : []),
    { x: s.t, y: s.y, name: "saída y", type: "scattergl", mode: "lines", line: { color: C.y, width: 2 } },
  ];
  const ctrl: Data[] = [
    ...(hasSat
      ? [{ x: s.t, y: s.u_cmd, name: "u comandado", type: "scattergl", mode: "lines", line: { color: C.ucmd, width: 1, dash: "dot", shape: "hv" }, opacity: 0.7, visible: "legendonly" } as Data]
      : []),
    { x: s.t, y: s.u, name: "u aplicado", type: "scattergl", mode: "lines", line: { color: C.u, width: 1.8, shape: "hv" } },
    ...(showDist && hasDist
      ? [
          { x: s.t, y: s.d_in, name: "pert. entrada", type: "scattergl", mode: "lines", line: { color: C.dist, width: 1.2 } } as Data,
          { x: s.t, y: s.d_out, name: "pert. saída", type: "scattergl", mode: "lines", line: { color: "#fb7185", width: 1.2 } } as Data,
        ]
      : []),
  ];

  return (
    <div className="sim-view">
      <div className="toolbar">
        <Toggle checked={showMeas} onChange={setShowMeas} label="Mostrar amostras medidas (com ruído)" />
        {hasDist && <Toggle checked={showDist} onChange={setShowDist} label="Mostrar perturbações" />}
        <span className="meta">
          {result.meta.n_samples.toLocaleString("pt-BR")} amostras · Ts = {result.meta.Ts} s · h = {Number(result.meta.h.toPrecision(4))} s · {result.meta.integration}
          {result.meta.decimated && ` · gráfico com ${result.meta.plotted_points.toLocaleString("pt-BR")} pontos`}
        </span>
      </div>
      {result.warnings.length > 0 && (
        <ul className="warnings">{result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
      )}
      <div className="grid2">
        <div className="panel"><Plot title="Referência e saída da planta" data={out} yTitle="y" uirevision="out" /></div>
        <div className="panel"><Plot title="Erro de controle e = r − y" data={[{ x: s.t, y: s.e, name: "erro e", type: "scattergl", mode: "lines", line: { color: C.e, width: 1.6 } }]} yTitle="e" uirevision="err" /></div>
        <div className="panel"><Plot title="Sinal de controle" data={ctrl} yTitle="u" uirevision="u" /></div>
        <div className="panel">
          {analysis ? (
            <Plot
              title="Resposta ao degrau unitário da planta (malha aberta)"
              data={[{ x: analysis.plant_step.t, y: analysis.plant_step.y, name: "G(s)·1/s", type: "scatter", mode: "lines", line: { color: "#34d399", width: 1.8 } }]}
              yTitle="y"
              uirevision="step"
            />
          ) : <div className="empty">Análise indisponível.</div>}
        </div>
      </div>
    </div>
  );
}
