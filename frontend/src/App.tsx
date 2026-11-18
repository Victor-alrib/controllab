import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, isAbort } from "./api/client";
import type { Analysis, Catalog, Run, SimConfig, SimResult } from "./types";
import { DEFAULT_CONFIG, RUN_COLORS, clone } from "./state/defaults";
import { ConfigPanel } from "./components/ConfigPanel";
import { MetricsPanel } from "./components/MetricsPanel";
import { HistoryPanel } from "./components/HistoryPanel";
import { SimulationView } from "./views/SimulationView";
import { TuningLab } from "./views/TuningLab";
import { CompareView } from "./views/CompareView";
import { AnalysisView } from "./views/AnalysisView";
import { exportCsv, loadConfigFile, openReport, saveConfig } from "./lib/export";

type Tab = "sim" | "tune" | "compare" | "analysis";
const TABS: { id: Tab; label: string }[] = [
  { id: "sim", label: "Simulação" },
  { id: "tune", label: "Sintonia PID" },
  { id: "compare", label: "Comparação" },
  { id: "analysis", label: "Análise" },
];

const LS_CONFIG = "controllab.config.v1";
const LS_HISTORY = "controllab.history.v1";

function loadLS<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v ? (JSON.parse(v) as T) : fallback;
  } catch {
    return fallback;
  }
}

export default function App() {
  const [catalog, setCatalog] = useState<Catalog>();
  const [catalogError, setCatalogError] = useState<string>();
  const [config, setConfigRaw] = useState<SimConfig>(() => loadLS(LS_CONFIG, DEFAULT_CONFIG));
  const [result, setResult] = useState<SimResult>();
  const [analysis, setAnalysis] = useState<Analysis>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("sim");
  const [runs, setRuns] = useState<Run[]>(() => loadLS<Run[]>(LS_HISTORY, []));
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [cmpLoading, setCmpLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController>();
  const attempted = useRef<Set<string>>(new Set());

  const setConfig = useCallback((fn: (c: SimConfig) => SimConfig) => setConfigRaw((c) => fn(c)), []);

  useEffect(() => {
    api.catalog().then(setCatalog).catch((e) => setCatalogError(String(e.message ?? e)));
  }, []);

  // ---- live simulation: re-run (debounced, cancellable) on every config change
  useEffect(() => {
    if (!catalog) return;
    localStorage.setItem(LS_CONFIG, JSON.stringify(config));
    const delay = tab === "tune" ? 60 : 200;
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setBusy(true);
      try {
        const [r, a] = await Promise.all([api.simulate(config, ac.signal), api.analyze(config, ac.signal).catch(() => undefined)]);
        setResult(r);
        setAnalysis(a);
        setError(undefined);
      } catch (e) {
        if (!isAbort(e)) setError(String((e as Error).message ?? e));
      } finally {
        if (abortRef.current === ac) setBusy(false);
      }
    }, delay);
    return () => clearTimeout(timer);
  }, [config, catalog, tab]);

  // ---- history persistence (configs + metrics only; signals are recomputed on demand)
  useEffect(() => {
    localStorage.setItem(LS_HISTORY, JSON.stringify(runs.map(({ result: _r, ...rest }) => rest)));
  }, [runs]);

  const register = useCallback(() => {
    if (!result) return;
    setRuns((rs) => {
      const n = rs.length ? Math.max(...rs.map((r) => Number(r.id.split("-")[1]) || 0)) + 1 : 1;
      const color = RUN_COLORS[(n - 1) % RUN_COLORS.length];
      const c = config.controller;
      const ctrlName = catalog?.controllers.find((x) => x.type === c.type)?.name ?? c.type;
      const gains = ["Kp", "Ki", "Kd"].filter((k) => c.params[k] !== undefined).map((k) => `${k}=${c.params[k]}`).join(" ");
      const run: Run = { id: `run-${n}`, label: `#${n} ${ctrlName} ${gains}`.trim(), color, createdAt: Date.now(), config: clone(config), metrics: result.metrics, result };
      setSelected((s) => new Set(s).add(run.id));
      return [run, ...rs];
    });
  }, [result, config, catalog]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        register();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [register]);

  // ---- ensure selected runs have signals (re-simulate runs restored from storage)
  const selectedRuns = useMemo(() => runs.filter((r) => selected.has(r.id)), [runs, selected]);
  useEffect(() => {
    const missing = selectedRuns.filter((r) => !r.result && !attempted.current.has(r.id));
    if (!missing.length) return;
    missing.forEach((r) => attempted.current.add(r.id));
    setCmpLoading(true);
    Promise.all(missing.map((r) => api.simulate(r.config).then((res) => [r.id, res] as const).catch(() => null)))
      .then((pairs) => {
        const map = new Map(pairs.filter(Boolean) as [string, SimResult][]);
        if (map.size) setRuns((rs) => rs.map((r) => (map.has(r.id) ? { ...r, result: map.get(r.id) } : r)));
      })
      .finally(() => setCmpLoading(false));
  }, [selectedRuns]);

  if (catalogError)
    return (
      <div className="fatal">
        <h2>Motor de simulação indisponível</h2>
        <p>{catalogError}</p>
        <p>Inicie o backend: <code>cd backend && uvicorn app.main:app --port 8000</code></p>
      </div>
    );
  if (!catalog) return <div className="fatal"><span className="spinner" /> Carregando…</div>;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="22" height="22"><path d="M3 23 C9 23 10 7 16 7 S22 15 29 15" stroke="#22d3ee" strokeWidth="2.6" fill="none" /><path d="M3 15 H29" stroke="#334155" strokeWidth="1.2" strokeDasharray="2 2" /></svg>
          <span>Control<b>Lab</b></span>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
              {t.label}
              {t.id === "compare" && selected.size > 0 && <span className="pill">{selected.size}</span>}
            </button>
          ))}
        </nav>
        <div className="actions">
          <span className={`status ${busy ? "busy" : error ? "err" : "ok"}`}>{busy ? "simulando…" : error ? "erro" : "pronto"}</span>
          <button className="btn primary" onClick={register} disabled={!result} title="Ctrl+Enter">Registrar</button>
          <div className="menu">
            <button className="btn">Arquivo ▾</button>
            <div className="menu-items">
              <button onClick={() => saveConfig(config)}>Salvar configuração (.json)</button>
              <button onClick={() => fileRef.current?.click()}>Carregar configuração…</button>
              <hr />
              <button onClick={() => exportCsv(config).catch((e) => setError(e.message))}>Exportar dados da simulação (.csv)</button>
              <button onClick={() => openReport([{ label: "Simulação atual", config }]).catch((e) => setError(e.message))}>Gerar relatório da simulação atual</button>
              <hr />
              <button onClick={() => { setConfigRaw(clone(DEFAULT_CONFIG)); }}>Restaurar configuração padrão</button>
            </div>
          </div>
          <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            try { setConfigRaw(await loadConfigFile(f)); } catch (err) { setError((err as Error).message); }
            e.target.value = "";
          }} />
        </div>
      </header>

      <aside className="left"><ConfigPanel catalog={catalog} config={config} setConfig={setConfig} /></aside>

      <main className="main">
        {error && <div className="error-bar">⚠ {error}</div>}
        {tab === "sim" && <SimulationView result={result} analysis={analysis} />}
        {tab === "tune" && <TuningLab catalog={catalog} config={config} setConfig={setConfig} result={result} analysis={analysis} busy={busy} onRegister={register} />}
        {tab === "compare" && <CompareView runs={selectedRuns} loading={cmpLoading} />}
        {tab === "analysis" && <AnalysisView analysis={analysis} Ts={config.settings.Ts} />}
      </main>

      <aside className="right">
        <div className="panel pad">
          <h4>Indicadores de desempenho</h4>
          <MetricsPanel metrics={result?.metrics} />
          {result?.meta.reference_type !== "step" && result && <p className="desc">Índices de resposta ao degrau são calculados apenas para referência em degrau.</p>}
        </div>
        <HistoryPanel
          runs={runs}
          selected={selected}
          toggle={(id) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; })}
          rename={(id, label) => setRuns((rs) => rs.map((r) => (r.id === id ? { ...r, label } : r)))}
          remove={(id) => { setRuns((rs) => rs.filter((r) => r.id !== id)); setSelected((s) => { const n = new Set(s); n.delete(id); return n; }); }}
          load={(r) => setConfigRaw(clone(r.config))}
          clear={() => { setRuns([]); setSelected(new Set()); }}
        />
      </aside>
    </div>
  );
}
