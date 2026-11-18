import type { Data } from "plotly.js";
import type { Run } from "../types";
import { Plot } from "../components/Plot";
import { METRIC_DEFS } from "../components/MetricsPanel";
import { fmt } from "../lib/format";
import { exportMetricsCsv, openReport } from "../lib/export";

export function CompareView({ runs, loading }: { runs: Run[]; loading: boolean }) {
  if (runs.length === 0)
    return <div className="empty big">Marque execuções no <b>Histórico</b> (painel à direita) para compará-las aqui.</div>;
  const ready = runs.filter((r) => r.result);

  const traces = (key: "y" | "e" | "u", withRef = false): Data[] => {
    const out: Data[] = [];
    ready.forEach((r, i) => {
      const s = r.result!.signals;
      if (withRef && i === 0)
        out.push({ x: s.t, y: s.r, name: "r", type: "scattergl", mode: "lines", line: { color: "#94a3b8", dash: "dash", width: 1.2 } });
      out.push({ x: s.t, y: s[key], name: r.label, type: "scattergl", mode: "lines", line: { color: r.color, width: 1.8, shape: key === "u" ? "hv" : "linear" } });
    });
    return out;
  };

  // best value per metric (by |value| for errors)
  const best: Record<string, number> = {};
  METRIC_DEFS.forEach((d) => {
    const vals = runs.map((r) => r.metrics[d.key] as number | null | undefined).filter((v): v is number => v !== null && v !== undefined && Number.isFinite(v)).map((v) => (d.abs ? Math.abs(v) : v));
    if (vals.length > 1) best[d.key] = d.lowerIsBetter ? Math.min(...vals) : Math.max(...vals);
  });

  return (
    <div className="compare">
      <div className="toolbar">
        <span className="meta">{runs.length} execuções selecionadas {loading && <span className="spinner" />}</span>
        <span style={{ flex: 1 }} />
        <button className="btn" onClick={() => exportMetricsCsv(runs)}>Exportar indicadores (CSV)</button>
        <button className="btn" onClick={() => openReport(runs.map((r) => ({ label: r.label, config: r.config })), "Comparação de simulações")}>Relatório da comparação</button>
      </div>
      <div className="panel"><Plot title="Saída y(t)" data={traces("y", true)} yTitle="y" height={320} uirevision="cmp-y" /></div>
      <div className="grid2">
        <div className="panel"><Plot title="Erro e(t)" data={traces("e")} yTitle="e" uirevision="cmp-e" /></div>
        <div className="panel"><Plot title="Controle u(t)" data={traces("u")} yTitle="u" uirevision="cmp-u" /></div>
      </div>
      <div className="panel pad">
        <table className="cmp-table">
          <thead>
            <tr><th>Indicador</th>{runs.map((r) => <th key={r.id}><span className="swatch" style={{ background: r.color }} />{r.label}</th>)}</tr>
          </thead>
          <tbody>
            {METRIC_DEFS.map((d) => (
              <tr key={d.key}>
                <td title={d.help}>{d.label}{d.unit ? ` [${d.unit}]` : ""}</td>
                {runs.map((r) => {
                  const v = r.metrics[d.key] as number | null | undefined;
                  const isBest = v !== null && v !== undefined && best[d.key] !== undefined && (d.abs ? Math.abs(v) : v) === best[d.key];
                  return <td key={r.id} className={isBest ? "best" : ""}>{fmt(v)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="desc">Destaque: melhor valor de cada indicador entre as execuções (menor, ou menor |e_ss|).</p>
      </div>
    </div>
  );
}
