import type { Run } from "../types";
import { fmt } from "../lib/format";

interface Props {
  runs: Run[];
  selected: Set<string>;
  toggle: (id: string) => void;
  rename: (id: string, label: string) => void;
  remove: (id: string) => void;
  load: (run: Run) => void;
  clear: () => void;
}

export function HistoryPanel({ runs, selected, toggle, rename, remove, load, clear }: Props) {
  return (
    <div className="history">
      <div className="history-head">
        <h3>Histórico <span className="count">{runs.length}</span></h3>
        {runs.length > 0 && <button className="btn tiny ghost" onClick={() => confirm("Apagar todo o histórico?") && clear()}>Limpar</button>}
      </div>
      {runs.length === 0 && <p className="desc">Use <b>Registrar</b> (ou Ctrl+Enter) para guardar a execução atual e compará-la depois.</p>}
      <ul>
        {runs.map((r) => (
          <li key={r.id} className={selected.has(r.id) ? "sel" : ""}>
            <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggle(r.id)} title="Incluir na comparação" />
            <span className="swatch" style={{ background: r.color }} />
            <div className="h-main">
              <input className="h-label" value={r.label} onChange={(e) => rename(r.id, e.target.value)} />
              <div className="h-sub">
                Mp {fmt(r.metrics.overshoot_pct, 3)}% · ts {fmt(r.metrics.settling_time, 3)}s · IAE {fmt(r.metrics.IAE, 3)}
              </div>
            </div>
            <button className="btn tiny ghost" title="Carregar esta configuração" onClick={() => load(r)}>↺</button>
            <button className="btn tiny ghost" title="Remover" onClick={() => remove(r.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
