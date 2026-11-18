import { api } from "../api/client";
import type { Run, SimConfig } from "../types";
import { METRIC_DEFS } from "../components/MetricsPanel";

export function download(name: string, data: Blob | string, mime = "text/plain") {
  const blob = typeof data === "string" ? new Blob([data], { type: mime }) : data;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

const stamp = () => new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");

export function saveConfig(cfg: SimConfig) {
  download(`controllab-config-${stamp()}.json`, JSON.stringify({ app: "ControlLab", version: 1, config: cfg }, null, 2), "application/json");
}

export async function loadConfigFile(file: File): Promise<SimConfig> {
  const j = JSON.parse(await file.text());
  const cfg = j.config ?? j;
  if (!cfg.plant || !cfg.controller || !cfg.settings) throw new Error("Arquivo não contém uma configuração ControlLab válida.");
  return cfg as SimConfig;
}

export async function exportCsv(cfg: SimConfig) {
  download(`controllab-dados-${stamp()}.csv`, await api.csv(cfg));
}

export function exportMetricsCsv(runs: Run[]) {
  const header = ["indicador", ...runs.map((r) => `"${r.label.replace(/"/g, "'")}"`)].join(",");
  const rows = METRIC_DEFS.map((d) => [d.label + (d.unit ? ` [${d.unit}]` : ""), ...runs.map((r) => {
    const v = r.metrics[d.key] as number | null | undefined;
    return v === null || v === undefined ? "" : String(v);
  })].join(","));
  download(`controllab-comparacao-${stamp()}.csv`, [header, ...rows].join("\n"), "text/csv");
}

export async function openReport(runs: { label: string; config: SimConfig }[], title = "Relatório ControlLab") {
  const html = await api.report({ title, runs });
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, "_blank");
  if (!w) download(`controllab-relatorio-${stamp()}.html`, blob);
}
