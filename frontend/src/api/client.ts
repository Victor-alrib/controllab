import type { Analysis, Catalog, SimConfig, SimResult } from "../types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {}

async function post<T>(path: string, body: unknown, signal?: AbortSignal, as: "json" | "text" | "blob" = "json"): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let msg = `Erro ${res.status}`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail))
        msg = j.detail
          .map((d: { loc?: string[]; msg: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`)
          .join("; ");
    } catch {
      /* ignore */
    }
    throw new ApiError(msg);
  }
  if (as === "text") return (await res.text()) as T;
  if (as === "blob") return (await res.blob()) as T;
  return (await res.json()) as T;
}

export const api = {
  async catalog(): Promise<Catalog> {
    const res = await fetch(`${BASE}/api/catalog`);
    if (!res.ok) throw new ApiError("Não foi possível carregar o catálogo do motor de simulação.");
    return res.json();
  },
  simulate: (cfg: SimConfig, signal?: AbortSignal) => post<SimResult>("/api/simulate", cfg, signal),
  analyze: (cfg: SimConfig, signal?: AbortSignal) => post<Analysis>("/api/analyze", cfg, signal),
  csv: (cfg: SimConfig) => post<Blob>("/api/export/csv", cfg, undefined, "blob"),
  report: (body: { title: string; author?: string; notes?: string; runs: { label: string; config: SimConfig }[] }) =>
    post<string>("/api/report", body, undefined, "text"),
};

export const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";
