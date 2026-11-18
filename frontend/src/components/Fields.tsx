import { useEffect, useState, type ReactNode } from "react";

/** Numeric input that keeps the raw text while typing and commits only valid numbers. */
export function NumberInput({
  value, onChange, min, max, step, disabled, title,
}: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; disabled?: boolean; title?: string }) {
  const [text, setText] = useState(String(value));
  const [bad, setBad] = useState(false);
  useEffect(() => {
    if (Number(text) !== value) setText(String(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <input
      className={`num ${bad ? "bad" : ""}`}
      type="text"
      inputMode="decimal"
      value={text}
      disabled={disabled}
      title={title}
      onChange={(e) => {
        const t = e.target.value.replace(",", ".");
        setText(t);
        const v = Number(t);
        const ok = t.trim() !== "" && Number.isFinite(v) && (min === undefined || v >= min) && (max === undefined || v <= max);
        setBad(!ok);
        if (ok) onChange(v);
      }}
      onKeyDown={(e) => {
        if (step && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
          e.preventDefault();
          const v = Number(Number(value + (e.key === "ArrowUp" ? step : -step)).toPrecision(12));
          if ((min === undefined || v >= min) && (max === undefined || v <= max)) onChange(v);
        }
      }}
      onBlur={() => {
        setText(String(value));
        setBad(false);
      }}
    />
  );
}

export function Row({ label, unit, hint, children }: { label: ReactNode; unit?: string; hint?: string; children: ReactNode }) {
  return (
    <label className="row" title={hint}>
      <span className="row-label">
        {label}
        {hint && <span className="hint-dot">?</span>}
      </span>
      <span className="row-input">
        {children}
        {unit && <span className="unit">{unit}</span>}
      </span>
    </label>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track"><span className="thumb" /></span>
      {label && <span>{label}</span>}
    </label>
  );
}

export function Section({ title, right, children, defaultOpen = true }: { title: string; right?: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="card">
      <header className="card-head" onClick={() => setOpen(!open)}>
        <span className={`chev ${open ? "open" : ""}`}>›</span>
        <h3>{title}</h3>
        <span className="card-right" onClick={(e) => e.stopPropagation()}>{right}</span>
      </header>
      {open && <div className="card-body">{children}</div>}
    </section>
  );
}
