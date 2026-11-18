import { useState } from "react";
import type { Data } from "plotly.js";
import type { Analysis, Catalog, SimConfig, SimResult } from "../types";
import { C, Plot } from "../components/Plot";
import { MetricsPanel } from "../components/MetricsPanel";
import { NumberInput } from "../components/Fields";
import { defaultParams } from "../state/defaults";
import { complexStr, fmt } from "../lib/format";

const GAINS = [
  { key: "Kp", label: "Kp", unit: "", color: "#22d3ee", initMax: 20 },
  { key: "Ki", label: "Ki", unit: "1/s", color: "#a78bfa", initMax: 10 },
  { key: "Kd", label: "Kd", unit: "s", color: "#34d399", initMax: 5 },
] as const;

interface Props {
  catalog: Catalog;
  config: SimConfig;
  setConfig: (fn: (c: SimConfig) => SimConfig) => void;
  result?: SimResult;
  analysis?: Analysis;
  busy: boolean;
  onRegister: () => void;
}

export function TuningLab({ catalog, config, setConfig, result, analysis, busy, onRegister }: Props) {
  const [maxes, setMaxes] = useState<Record<string, number>>({ Kp: 20, Ki: 10, Kd: 5 });
  const [baseline, setBaseline] = useState<{ result: SimResult; gains: Record<string, number> } | null>(null);
  const type = config.controller.type;
  const params = config.controller.params;

  if (!["p", "pi", "pid"].includes(type)) {
    return (
      <div className="empty big">
        <p>O laboratório de sintonia trabalha com controladores P, PI ou PID.</p>
        <button className="btn primary" onClick={() => setConfig((c) => ({ ...c, controller: { type: "pid", params: defaultParams(catalog.controllers.find((x) => x.type === "pid")!) } }))}>
          Usar PID
        </button>
      </div>
    );
  }
  const available = GAINS.filter((g) => g.key === "Kp" || (g.key === "Ki" && type !== "p") || (g.key === "Kd" && type === "pid"));
  const setGain = (k: string, v: number) => setConfig((c) => ({ ...c, controller: { ...c.controller, params: { ...c.controller.params, [k]: v } } }));
  const gains = Object.fromEntries(available.map((g) => [g.key, Number(params[g.key] ?? 0)]));

  const s = result?.signals;
  const b = baseline?.result.signals;
  const outData: Data[] = s ? [
    { x: s.t, y: s.r, name: "r", type: "scattergl", mode: "lines", line: { color: C.ref, dash: "dash", width: 1.2 } },
    ...(b ? [{ x: b.t, y: b.y, name: "y (referência fixada)", type: "scattergl", mode: "lines", line: { color: "#64748b", width: 1.6 } } as Data] : []),
    { x: s.t, y: s.y, name: "y (atual)", type: "scattergl", mode: "lines", line: { color: C.y, width: 2.2 } },
  ] : [];
  const uData: Data[] = s ? [
    ...(b ? [{ x: b.t, y: b.u, name: "u (referência fixada)", type: "scattergl", mode: "lines", line: { color: "#64748b", width: 1.4, shape: "hv" } } as Data] : []),
    { x: s.t, y: s.u, name: "u (atual)", type: "scattergl", mode: "lines", line: { color: C.u, width: 1.8, shape: "hv" } },
  ] : [];
  const cl = analysis?.closed_loop;
  const circle = Array.from({ length: 121 }, (_, i) => (i * 2 * Math.PI) / 120);

  return (
    <div className="tuning">
      <div className="tuning-side">
        <div className="panel pad">
          <h4>Ganhos {busy && <span className="spinner" />}</h4>
          {available.map((g) => {
            const v = gains[g.key];
            const max = Math.max(maxes[g.key], v);
            return (
              <div className="slider" key={g.key}>
                <div className="slider-head">
                  <span className="gain-name" style={{ color: g.color }}>{g.label}</span>
                  <NumberInput value={v} min={g.key === "Kp" ? undefined : 0} onChange={(x) => setGain(g.key, x)} step={max / 100} />
                  <span className="unit">{g.unit}</span>
                  {baseline && baseline.gains[g.key] !== undefined && <span className="was">ref: {fmt(baseline.gains[g.key])}</span>}
                </div>
                <input type="range" min={0} max={max} step={max / 1000} value={v} onChange={(e) => setGain(g.key, Number(e.target.value))} style={{ accentColor: g.color }} />
                <div className="slider-range">
                  <span>0</span>
                  <span className="max-edit">máx <NumberInput value={maxes[g.key]} min={1e-6} onChange={(x) => setMaxes((m) => ({ ...m, [g.key]: x }))} /></span>
                </div>
              </div>
            );
          })}
          <div className="btn-row">
            <button className="btn" disabled={!result} onClick={() => result && setBaseline({ result, gains })}>📌 Fixar como referência</button>
            {baseline && <button className="btn ghost" onClick={() => setBaseline(null)}>Limpar</button>}
          </div>
          <button className="btn primary wide" disabled={!result} onClick={onRegister}>Registrar no histórico</button>
        </div>
        <div className="panel pad">
          <h4>Indicadores {baseline && <span className="sub">(Δ vs. referência fixada)</span>}</h4>
          <MetricsPanel metrics={result?.metrics} baseline={baseline?.result.metrics} />
        </div>
        <details className="panel pad edu">
          <summary>Efeito típico do aumento de cada ganho</summary>
          <table>
            <thead><tr><th></th><th>tr</th><th>Mp</th><th>ts</th><th>ess</th></tr></thead>
            <tbody>
              <tr><td>Kp ↑</td><td>↓</td><td>↑</td><td>~</td><td>↓</td></tr>
              <tr><td>Ki ↑</td><td>↓</td><td>↑</td><td>↑</td><td>elimina</td></tr>
              <tr><td>Kd ↑</td><td>~</td><td>↓</td><td>↓</td><td>—</td></tr>
            </tbody>
          </table>
          <p className="desc">Tendências qualitativas para plantas simples estáveis; não são regras universais. Verifique sempre nos gráficos e nos polos ao lado.</p>
        </details>
      </div>
      <div className="tuning-main">
        <div className="panel"><Plot title="Saída da planta" data={outData} yTitle="y" height={330} uirevision="tune-y" /></div>
        <div className="grid2">
          <div className="panel"><Plot title="Sinal de controle" data={uData} yTitle="u" height={260} uirevision="tune-u" /></div>
          <div className="panel">
            {cl ? (
              <Plot
                title={`Polos de MF no plano z — ${cl.discrete_stable ? "estável" : "INSTÁVEL"} (max|z| = ${fmt(cl.spectral_radius, 4)})`}
                data={[
                  { x: circle.map(Math.cos), y: circle.map(Math.sin), name: "|z|=1", type: "scatter", mode: "lines", line: { color: "#334155", width: 1 }, hoverinfo: "skip", showlegend: false },
                  { x: cl.discrete_poles.map((p) => p.re), y: cl.discrete_poles.map((p) => p.im), text: cl.discrete_poles.map((p) => complexStr(p.re, p.im)), name: "polos", type: "scatter", mode: "markers", marker: { symbol: "x", size: 11, color: cl.discrete_stable ? "#f59e0b" : "#ef4444", line: { width: 2 } }, hovertemplate: "%{text}<extra></extra>" },
                ]}
                xTitle="Re" yTitle="Im" height={260}
                layout={{ hovermode: "closest", showlegend: false, xaxis: { range: [-1.3, 1.3] }, yaxis: { scaleanchor: "x", range: [-1.1, 1.1] } }}
                uirevision="tune-z"
              />
            ) : <div className="empty">—</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
