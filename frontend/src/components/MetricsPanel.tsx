import type { Metrics } from "../types";
import { fmt } from "../lib/format";

export interface MetricDef {
  key: keyof Metrics;
  label: string;
  short: string;
  unit?: string;
  lowerIsBetter: boolean;
  abs?: boolean;
  help: string;
}

export const METRIC_DEFS: MetricDef[] = [
  { key: "overshoot_pct", label: "Overshoot", short: "Mp", unit: "%", lowerIsBetter: true, help: "(y_pico − y_final)/(y_final − y_0) · 100" },
  { key: "rise_time", label: "Tempo de subida", short: "tr", unit: "s", lowerIsBetter: true, help: "Intervalo entre 10% e 90% da variação final" },
  { key: "settling_time", label: "Tempo de acomodação", short: "ts", unit: "s", lowerIsBetter: true, help: "Último instante fora da faixa ±banda em torno do valor final" },
  { key: "peak_time", label: "Tempo de pico", short: "tp", unit: "s", lowerIsBetter: true, help: "Instante do valor máximo da saída" },
  { key: "steady_state_error", label: "Erro em regime", short: "ess", lowerIsBetter: true, abs: true, help: "r_final − y_final" },
  { key: "final_error", label: "Erro final e(t_f)", short: "e(tf)", lowerIsBetter: true, abs: true, help: "Erro no último instante simulado (inclui efeito de perturbações)" },
  { key: "IAE", label: "IAE", short: "IAE", lowerIsBetter: true, help: "∫|e(t)| dt" },
  { key: "ISE", label: "ISE", short: "ISE", lowerIsBetter: true, help: "∫e(t)² dt" },
  { key: "ITAE", label: "ITAE", short: "ITAE", lowerIsBetter: true, help: "∫t·|e(t)| dt" },
  { key: "u_max_abs", label: "Pico de controle", short: "max|u|", lowerIsBetter: true, help: "max |u(t)| aplicado" },
  { key: "control_energy", label: "Esforço de controle", short: "∫u²", lowerIsBetter: true, help: "∫u(t)² dt" },
  { key: "total_variation", label: "Variação total", short: "TV", lowerIsBetter: true, help: "Σ|u_k − u_{k−1}| (agressividade/ruído no atuador)" },
  { key: "saturation_pct", label: "Tempo saturado", short: "sat", unit: "%", lowerIsBetter: true, help: "Fração das amostras com atuador saturado" },
];

const PRIMARY: (keyof Metrics)[] = ["overshoot_pct", "rise_time", "settling_time", "steady_state_error", "IAE", "ISE", "ITAE"];

export function MetricsPanel({ metrics, baseline, compact }: { metrics?: Metrics; baseline?: Metrics; compact?: boolean }) {
  if (!metrics) return <div className="empty">Sem resultados.</div>;
  const defs = compact ? METRIC_DEFS.filter((d) => PRIMARY.includes(d.key)) : METRIC_DEFS;
  return (
    <div className="metrics">
      {!metrics.stable_run && <div className="badge danger">Simulação divergiu — malha instável</div>}
      {metrics.settled === false && metrics.stable_run && metrics.overshoot_pct !== undefined && (
        <div className="badge warn">Regime não atingido na janela</div>
      )}
      {defs.map((d) => {
        const v = metrics[d.key] as number | null | undefined;
        if (v === undefined) return null;
        const b = baseline?.[d.key] as number | null | undefined;
        let delta: JSX.Element | null = null;
        if (baseline && v !== null && b !== null && b !== undefined && Number.isFinite(b)) {
          const cur = d.abs ? Math.abs(v) : v, ref = d.abs ? Math.abs(b) : b;
          const diff = cur - ref;
          if (Math.abs(diff) > 1e-12 * Math.max(1, Math.abs(ref))) {
            const better = d.lowerIsBetter ? diff < 0 : diff > 0;
            delta = <span className={`delta ${better ? "good" : "bad"}`}>{diff > 0 ? "▲" : "▼"} {fmt(Math.abs(diff), 3)}</span>;
          }
        }
        return (
          <div className="metric" key={d.key} title={d.help}>
            <span className="m-label">{d.label}</span>
            <span className="m-value">
              {fmt(v)}
              {d.unit && v !== null && <span className="m-unit">{d.unit}</span>}
            </span>
            {delta}
          </div>
        );
      })}
    </div>
  );
}
