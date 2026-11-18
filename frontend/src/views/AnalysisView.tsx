import type { Data } from "plotly.js";
import type { Analysis, PoleInfo } from "../types";
import { Plot } from "../components/Plot";
import { complexStr, fmt, polyToString } from "../lib/format";

export function AnalysisView({ analysis, Ts }: { analysis?: Analysis; Ts: number }) {
  if (!analysis) return <div className="empty big">Análise indisponível.</div>;
  const a = analysis;
  const cl = a.closed_loop;
  const circle = Array.from({ length: 181 }, (_, i) => (i * 2 * Math.PI) / 180);

  const sPlane: Data[] = [
    { x: a.plant.poles.map((p) => p.re), y: a.plant.poles.map((p) => p.im), name: "polos G(s)", type: "scatter", mode: "markers", marker: { symbol: "x", size: 11, color: "#94a3b8", line: { width: 2 } } },
    { x: a.plant.zeros.map((z) => z[0]), y: a.plant.zeros.map((z) => z[1]), name: "zeros G(s)", type: "scatter", mode: "markers", marker: { symbol: "circle-open", size: 11, color: "#94a3b8", line: { width: 2 } } },
    ...(cl ? [{ x: cl.continuous_poles.map((p) => p.re), y: cl.continuous_poles.map((p) => p.im), name: "polos MF (contínuo)", type: "scatter", mode: "markers", marker: { symbol: "x", size: 11, color: "#22d3ee", line: { width: 2 } } } as Data] : []),
  ];
  const zPlane: Data[] = cl
    ? [
        { x: circle.map(Math.cos), y: circle.map(Math.sin), name: "|z| = 1", type: "scatter", mode: "lines", line: { color: "#334155", width: 1 }, hoverinfo: "skip" },
        { x: cl.discrete_poles.map((p) => p.re), y: cl.discrete_poles.map((p) => p.im), name: "polos MF (z)", type: "scatter", mode: "markers", marker: { symbol: "x", size: 11, color: cl.discrete_stable ? "#f59e0b" : "#ef4444", line: { width: 2 } } },
      ]
    : [];

  const f = a.open_loop_freq;
  const m = a.margins;
  return (
    <div className="analysis">
      <div className="cards3">
        <div className="panel pad">
          <h4>Planta G(s)</h4>
          <div className="tf">
            <div className="tf-num">{polyToString(a.plant.num)}</div>
            <div className="tf-bar" />
            <div className="tf-den">{polyToString(a.plant.den)}</div>
          </div>
          {a.plant.delay > 0 && <div className="kv"><span>Atraso</span><b>e^(−{fmt(a.plant.delay)}s)</b></div>}
          <div className="kv"><span>Ganho DC G(0)</span><b>{a.plant.dc_gain === null ? "∞ (integrador)" : fmt(a.plant.dc_gain)}</b></div>
          <div className="kv"><span>Estabilidade (MA)</span><b className={a.plant.stable ? "ok" : "bad"}>{a.plant.stable ? "estável" : "não assintoticamente estável"}</b></div>
          <PoleTable title="Polos" poles={a.plant.poles} />
        </div>
        <div className="panel pad">
          <h4>Malha fechada</h4>
          {!cl ? <p className="desc">Não aplicável.</p> : (
            <>
              <div className="kv"><span>Sistema amostrado (Ts = {Ts} s)</span><b className={cl.discrete_stable ? "ok" : "bad"}>{cl.discrete_stable ? "estável" : "INSTÁVEL"}</b></div>
              <div className="kv"><span>Raio espectral max|z|</span><b>{fmt(cl.spectral_radius, 5)}</b></div>
              <div className="kv"><span>Equivalente contínuo</span><b className={cl.continuous_stable ? "ok" : "bad"}>{cl.continuous_stable ? "estável" : "instável"}</b></div>
              <PoleTable title="Polos discretos (exatos p/ a simulação linear)" poles={cl.discrete_poles} discrete />
            </>
          )}
        </div>
        <div className="panel pad">
          <h4>Margens de estabilidade</h4>
          {m ? (
            <>
              <div className="kv"><span>Margem de ganho</span><b>{m.gain_margin_db === null ? "∞" : `${fmt(m.gain_margin_db)} dB`}</b></div>
              <div className="kv"><span>  em ω</span><b>{fmt(m.w_phase_crossover)} rad/s</b></div>
              <div className="kv"><span>Margem de fase</span><b>{m.phase_margin_deg === null ? "∞" : `${fmt(m.phase_margin_deg)}°`}</b></div>
              <div className="kv"><span>  em ω</span><b>{fmt(m.w_gain_crossover)} rad/s</b></div>
              <p className="desc">Calculadas sobre L(jω) = C_y(jω)·G(jω)·e^(−jωθ) em tempo contínuo, com atraso exato.</p>
            </>
          ) : <p className="desc">Sem realimentação (malha aberta).</p>}
          {a.notes.map((n, i) => <p key={i} className="note">{n}</p>)}
        </div>
      </div>
      <div className="grid2">
        <div className="panel"><Plot title="Plano s — polos e zeros" data={sPlane} xTitle="Re" yTitle="Im" layout={{ hovermode: "closest", yaxis: { scaleanchor: "x" } }} uirevision="s" /></div>
        <div className="panel">{cl ? <Plot title="Plano z — polos de malha fechada" data={zPlane} xTitle="Re" yTitle="Im" layout={{ hovermode: "closest", yaxis: { scaleanchor: "x" } }} uirevision="z" /> : <div className="empty">—</div>}</div>
        {f && (
          <>
            <div className="panel"><Plot title="Bode de L(jω) — módulo" data={[{ x: f.w, y: f.mag_db, name: "|L| dB", type: "scatter", mode: "lines", line: { color: "#22d3ee" } }]} xTitle="ω [rad/s]" yTitle="dB" layout={{ xaxis: { type: "log" }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: "#475569", dash: "dot" } }] }} uirevision="bm" /></div>
            <div className="panel"><Plot title="Bode de L(jω) — fase" data={[{ x: f.w, y: f.phase_deg, name: "∠L", type: "scatter", mode: "lines", line: { color: "#f59e0b" } }]} xTitle="ω [rad/s]" yTitle="graus" layout={{ xaxis: { type: "log" }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: -180, y1: -180, line: { color: "#475569", dash: "dot" } }] }} uirevision="bp" /></div>
          </>
        )}
      </div>
    </div>
  );
}

function PoleTable({ title, poles, discrete }: { title: string; poles: PoleInfo[]; discrete?: boolean }) {
  return (
    <div className="poles">
      <div className="pgroup-title">{title}</div>
      <table>
        <thead><tr><th>{discrete ? "z" : "s"}</th>{discrete && <th>|z|</th>}<th>ωn</th><th>ζ</th></tr></thead>
        <tbody>
          {poles.slice(0, 12).map((p, i) => (
            <tr key={i}><td>{complexStr(p.re, p.im)}</td>{discrete && <td>{fmt(p.mag)}</td>}<td>{fmt(p.wn, 3)}</td><td>{fmt(p.zeta, 3)}</td></tr>
          ))}
        </tbody>
      </table>
      {poles.length > 12 && <div className="desc">+{poles.length - 12} polos</div>}
    </div>
  );
}
