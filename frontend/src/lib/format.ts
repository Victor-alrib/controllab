export function fmt(v: number | null | undefined, digits = 4): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e5 || a < 1e-3) return v.toExponential(digits - 1);
  return Number(v.toPrecision(digits)).toString();
}

export function polyToString(c: number[], v = "s"): string {
  const n = c.length - 1;
  const terms: string[] = [];
  c.forEach((coef, i) => {
    const p = n - i;
    if (Math.abs(coef) < 1e-12) return;
    const a = Math.abs(coef);
    const sign = coef < 0 ? "−" : "+";
    const num = a === 1 && p > 0 ? "" : fmt(a, 4);
    const pow = p === 0 ? "" : p === 1 ? v : `${v}${superscript(p)}`;
    terms.push(`${sign} ${num}${pow}`);
  });
  if (!terms.length) return "0";
  let s = terms.join(" ");
  s = s.startsWith("+ ") ? s.slice(2) : "−" + s.slice(2);
  return s;
}

const SUP: Record<string, string> = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹" };
const superscript = (n: number) => String(n).split("").map((d) => SUP[d]).join("");

export function complexStr(re: number, im: number): string {
  if (Math.abs(im) < 1e-10) return fmt(re);
  return `${fmt(re)} ${im >= 0 ? "+" : "−"} ${fmt(Math.abs(im))}j`;
}
