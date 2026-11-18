import { useRef } from "react";
import type { Catalog, DisturbanceConfig, Params, SimConfig } from "../types";
import { NEW_DISTURBANCE, defaultParams } from "../state/defaults";
import { NumberInput, Row, Section, Toggle } from "./Fields";
import { ParamForm } from "./ParamForm";

interface Props {
  catalog: Catalog;
  config: SimConfig;
  setConfig: (fn: (c: SimConfig) => SimConfig) => void;
}

export function ConfigPanel({ catalog, config, setConfig }: Props) {
  // remembers parameters per model type when the user switches back and forth
  const cache = useRef<Record<string, Params>>({});
  const plantDesc = catalog.plants.find((p) => p.type === config.plant.type)!;
  const ctrlDesc = catalog.controllers.find((c) => c.type === config.controller.type)!;

  const switchModel = (kind: "plant" | "controller", type: string) => {
    const list = kind === "plant" ? catalog.plants : catalog.controllers;
    const desc = list.find((d) => d.type === type)!;
    setConfig((c) => {
      cache.current[`${kind}:${c[kind].type}`] = c[kind].params;
      return { ...c, [kind]: { type, params: cache.current[`${kind}:${type}`] ?? defaultParams(desc) } };
    });
  };

  const upd = <K extends keyof SimConfig>(k: K, patch: Partial<SimConfig[K]>) =>
    setConfig((c) => ({ ...c, [k]: { ...(c[k] as object), ...patch } }));
  const ref = config.reference;
  const st = config.settings;

  const setDist = (i: number, patch: Partial<DisturbanceConfig>) =>
    setConfig((c) => ({ ...c, disturbances: c.disturbances.map((d, j) => (j === i ? { ...d, ...patch } : d)) }));

  return (
    <div className="config">
      <Section title="Planta">
        <select className="model-select" value={config.plant.type} onChange={(e) => switchModel("plant", e.target.value)}>
          {catalog.plants.map((p) => <option key={p.type} value={p.type}>{p.name}</option>)}
        </select>
        <div className="eq">{plantDesc.equation ? <Equation tex={plantDesc.equation} /> : null}</div>
        <p className="desc">{plantDesc.description}</p>
        <ParamForm specs={plantDesc.params} values={config.plant.params}
          onChange={(p) => setConfig((c) => ({ ...c, plant: { ...c.plant, params: p } }))} />
      </Section>

      <Section title="Controlador">
        <select className="model-select" value={config.controller.type} onChange={(e) => switchModel("controller", e.target.value)}>
          <optgroup label="Disponíveis">
            {catalog.controllers.filter((c) => c.status !== "planned").map((c) => <option key={c.type} value={c.type}>{c.name}</option>)}
          </optgroup>
          <optgroup label="Em desenvolvimento">
            {catalog.controllers.filter((c) => c.status === "planned").map((c) => (
              <option key={c.type} value={c.type} disabled>{c.name} — planejado</option>
            ))}
          </optgroup>
        </select>
        <div className="eq">{ctrlDesc.equation ? <Equation tex={ctrlDesc.equation} /> : null}</div>
        <p className="desc">{ctrlDesc.description}</p>
        <ParamForm specs={ctrlDesc.params} values={config.controller.params}
          onChange={(p) => setConfig((c) => ({ ...c, controller: { ...c.controller, params: p } }))} />
      </Section>

      <Section title="Referência">
        <Row label="Tipo">
          <select value={ref.type} onChange={(e) => upd("reference", { type: e.target.value as SimConfig["reference"]["type"] })}>
            <option value="step">Degrau</option>
            <option value="ramp">Rampa</option>
            <option value="sine">Senoide</option>
            <option value="square">Onda quadrada</option>
            <option value="constant">Constante</option>
          </select>
        </Row>
        {ref.type !== "ramp" && (
          <Row label={ref.type === "step" || ref.type === "constant" ? "Valor final" : "Amplitude"}>
            <NumberInput value={ref.amplitude} onChange={(v) => upd("reference", { amplitude: v })} step={0.1} />
          </Row>
        )}
        {ref.type === "ramp" && (
          <Row label="Inclinação" unit="1/s"><NumberInput value={ref.slope} onChange={(v) => upd("reference", { slope: v })} step={0.1} /></Row>
        )}
        {(ref.type === "sine" || ref.type === "square") && (
          <Row label="Frequência" unit="Hz"><NumberInput value={ref.frequency} min={1e-6} onChange={(v) => upd("reference", { frequency: v })} step={0.05} /></Row>
        )}
        {ref.type !== "constant" && (
          <>
            <Row label={ref.type === "step" ? "Valor inicial" : "Offset"}>
              <NumberInput value={ref.initial} onChange={(v) => upd("reference", { initial: v })} step={0.1} />
            </Row>
            <Row label="Instante de início" unit="s"><NumberInput value={ref.time} min={0} onChange={(v) => upd("reference", { time: v })} step={0.1} /></Row>
          </>
        )}
      </Section>

      <Section title="Simulação">
        <Row label="Tempo de simulação" unit="s"><NumberInput value={st.t_final} min={1e-6} onChange={(v) => upd("settings", { t_final: v })} step={1} /></Row>
        <Row label="Amostragem Ts" unit="s" hint="Período do controlador digital. A planta é integrada exatamente (ZOH) entre amostras.">
          <NumberInput value={st.Ts} min={1e-6} onChange={(v) => upd("settings", { Ts: v })} step={0.001} />
        </Row>
        <Row label="Faixa de acomodação" unit="%">
          <NumberInput value={st.settling_band * 100} min={0.1} max={49} onChange={(v) => upd("settings", { settling_band: v / 100 })} step={0.5} />
        </Row>
        <div className="info">{Math.round(st.t_final / st.Ts).toLocaleString("pt-BR")} amostras</div>
      </Section>

      <Section title="Saturação do atuador" defaultOpen={config.saturation.enabled}
        right={<Toggle checked={config.saturation.enabled} onChange={(v) => upd("saturation", { enabled: v })} />}>
        <Row label="u mínimo"><NumberInput value={config.saturation.u_min} onChange={(v) => upd("saturation", { u_min: v })} step={0.5} disabled={!config.saturation.enabled} /></Row>
        <Row label="u máximo"><NumberInput value={config.saturation.u_max} onChange={(v) => upd("saturation", { u_max: v })} step={0.5} disabled={!config.saturation.enabled} /></Row>
      </Section>

      <Section title={`Perturbações (${config.disturbances.filter((d) => d.enabled).length})`} defaultOpen={config.disturbances.length > 0}
        right={<button className="btn tiny" onClick={() => setConfig((c) => ({ ...c, disturbances: [...c.disturbances, { ...NEW_DISTURBANCE }] }))}>+ Adicionar</button>}>
        {config.disturbances.length === 0 && <p className="desc">Nenhuma perturbação. Use “+ Adicionar” para inserir uma perturbação na entrada ou na saída da planta.</p>}
        {config.disturbances.map((d, i) => (
          <div key={i} className="dist">
            <div className="dist-head">
              <Toggle checked={d.enabled} onChange={(v) => setDist(i, { enabled: v })} label={`#${i + 1}`} />
              <select value={d.target} onChange={(e) => setDist(i, { target: e.target.value as DisturbanceConfig["target"] })}>
                <option value="input">na entrada (carga)</option>
                <option value="output">na saída</option>
              </select>
              <button className="btn tiny ghost" onClick={() => setConfig((c) => ({ ...c, disturbances: c.disturbances.filter((_, j) => j !== i) }))}>✕</button>
            </div>
            <Row label="Forma">
              <select value={d.shape} onChange={(e) => setDist(i, { shape: e.target.value as DisturbanceConfig["shape"] })}>
                <option value="step">Degrau</option>
                <option value="pulse">Pulso</option>
                <option value="sine">Senoide</option>
              </select>
            </Row>
            <Row label="Amplitude"><NumberInput value={d.amplitude} onChange={(v) => setDist(i, { amplitude: v })} step={0.1} /></Row>
            <Row label="Início" unit="s"><NumberInput value={d.time} min={0} onChange={(v) => setDist(i, { time: v })} step={0.5} /></Row>
            {d.shape === "pulse" && <Row label="Duração" unit="s"><NumberInput value={d.duration} min={1e-6} onChange={(v) => setDist(i, { duration: v })} step={0.1} /></Row>}
            {d.shape === "sine" && <Row label="Frequência" unit="Hz"><NumberInput value={d.frequency} min={1e-6} onChange={(v) => setDist(i, { frequency: v })} step={0.1} /></Row>}
          </div>
        ))}
      </Section>

      <Section title="Ruído de medição" defaultOpen={config.noise.enabled}
        right={<Toggle checked={config.noise.enabled} onChange={(v) => upd("noise", { enabled: v })} />}>
        <Row label="Desvio padrão σ" hint="Ruído branco gaussiano somado à medição usada pelo controlador.">
          <NumberInput value={config.noise.std} min={0} onChange={(v) => upd("noise", { std: v })} step={0.005} disabled={!config.noise.enabled} />
        </Row>
        <Row label="Semente" hint="Mesma semente → mesma realização do ruído (simulações reprodutíveis).">
          <NumberInput value={config.noise.seed} min={0} onChange={(v) => upd("noise", { seed: Math.round(v) })} step={1} disabled={!config.noise.enabled} />
        </Row>
      </Section>
    </div>
  );
}

export function Equation({ tex }: { tex: string }) {
  return <code>{tex}</code>;
}
