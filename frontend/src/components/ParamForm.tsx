import { useEffect, useState } from "react";
import type { ParamSpec, Params } from "../types";
import { NumberInput, Row, Toggle } from "./Fields";

/** Renders a form from backend ParamSpec descriptors (no per-model UI code). */
export function ParamForm({ specs, values, onChange }: { specs: ParamSpec[]; values: Params; onChange: (p: Params) => void }) {
  const set = (k: string, v: unknown) => onChange({ ...values, [k]: v });
  const basic = specs.filter((s) => !s.advanced);
  const adv = specs.filter((s) => s.advanced);

  const renderGroup = (list: ParamSpec[]) => {
    const groups: Record<string, ParamSpec[]> = {};
    list.forEach((s) => (groups[s.group] ??= []).push(s));
    const multi = Object.keys(groups).length > 1;
    return Object.entries(groups).map(([g, items]) => (
      <div key={g} className="pgroup">
        {multi && <div className="pgroup-title">{g}</div>}
        {items.map((s) => (
          <Field key={s.key} spec={s} value={values[s.key] ?? s.default} onChange={(v) => set(s.key, v)} />
        ))}
      </div>
    ));
  };

  return (
    <div className="pform">
      {renderGroup(basic)}
      {adv.length > 0 && (
        <details className="adv">
          <summary>Parâmetros avançados</summary>
          {renderGroup(adv)}
        </details>
      )}
    </div>
  );
}

function Field({ spec, value, onChange }: { spec: ParamSpec; value: unknown; onChange: (v: unknown) => void }) {
  switch (spec.kind) {
    case "float":
    case "int": {
      const min = spec.min !== undefined && spec.exclusive_min ? spec.min + Number.EPSILON : spec.min;
      return (
        <Row label={spec.label} unit={spec.unit} hint={spec.description}>
          <NumberInput value={Number(value)} onChange={onChange} min={min} max={spec.max} step={spec.step} />
        </Row>
      );
    }
    case "bool":
      return (
        <Row label={spec.label} hint={spec.description}>
          <Toggle checked={Boolean(value)} onChange={onChange} />
        </Row>
      );
    case "select":
      return (
        <Row label={spec.label} hint={spec.description}>
          <select value={String(value)} onChange={(e) => onChange(e.target.value)}>
            {spec.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </Row>
      );
    case "vector":
      return <VectorField spec={spec} value={value as number[]} onChange={onChange} />;
    case "matrix":
      return <MatrixField spec={spec} value={value as number[][]} onChange={onChange} />;
  }
}

function VectorField({ spec, value, onChange }: { spec: ParamSpec; value: number[]; onChange: (v: number[]) => void }) {
  const [text, setText] = useState(value.join(", "));
  const [bad, setBad] = useState(false);
  useEffect(() => {
    if (JSON.stringify(parseVec(text)) !== JSON.stringify(value)) setText(value.join(", "));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <div className="vfield" title={spec.description}>
      <div className="row-label">{spec.label}</div>
      <input
        className={`mono ${bad ? "bad" : ""}`}
        value={text}
        placeholder="1, 3, 2"
        onChange={(e) => {
          setText(e.target.value);
          const parts = parseVec(e.target.value);
          const ok = parts.length > 0 && parts.every(Number.isFinite);
          setBad(!ok);
          if (ok) onChange(parts);
        }}
      />
      {spec.description && <div className="desc">{spec.description}</div>}
    </div>
  );
}

/** MATLAB-style matrix entry: rows separated by ';' or newlines, e.g. "0 1; -2 -3". */
function MatrixField({ spec, value, onChange }: { spec: ParamSpec; value: number[][]; onChange: (v: number[][]) => void }) {
  const toText = (m: number[][]) => m.map((r) => r.join(" ")).join("; ");
  const [text, setText] = useState(toText(value));
  const [bad, setBad] = useState(false);
  useEffect(() => {
    if (JSON.stringify(parseMat(text)) !== JSON.stringify(value)) setText(toText(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <div className="vfield">
      <div className="row-label">{spec.label}</div>
      <input
        className={`mono ${bad ? "bad" : ""}`}
        value={text}
        placeholder="0 1; -2 -3"
        onChange={(e) => {
          setText(e.target.value);
          const rows = parseMat(e.target.value);
          const ok = rows.length > 0 && rows.every((r) => r.length === rows[0].length && r.every(Number.isFinite));
          setBad(!ok);
          if (ok) onChange(rows);
        }}
      />
    </div>
  );
}

const parseVec = (t: string) => t.split(/[\s,;]+/).filter(Boolean).map(Number);
const parseMat = (t: string) =>
  t.split(/[;\n]/).map((r) => r.trim()).filter(Boolean).map((r) => r.split(/[\s,]+/).filter(Boolean).map(Number));
