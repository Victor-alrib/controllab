import type { DisturbanceConfig, ModelDescriptor, Params, SimConfig } from "../types";

export const DEFAULT_CONFIG: SimConfig = {
  plant: { type: "second_order", params: { K: 1, wn: 2, zeta: 0.3, y0: 0, dy0: 0, delay: 0 } },
  controller: {
    type: "pid",
    params: { Kp: 2, Ki: 1.5, Kd: 0.4, Tf: 0.01, b: 1, c: 1, integration: "forward", anti_windup: "back_calculation", Kt: 1 },
  },
  reference: { type: "step", amplitude: 1, initial: 0, time: 0, slope: 1, frequency: 0.2 },
  disturbances: [],
  noise: { enabled: false, std: 0.01, seed: 0 },
  saturation: { enabled: false, u_min: -10, u_max: 10 },
  settings: { t_final: 10, Ts: 0.01, settling_band: 0.02, max_plot_points: 6000 },
};

export const NEW_DISTURBANCE: DisturbanceConfig = {
  enabled: true, target: "input", shape: "step", amplitude: 0.5, time: 5, duration: 1, frequency: 1,
};

export function defaultParams(desc: ModelDescriptor): Params {
  const p: Params = {};
  for (const s of desc.params) p[s.key] = s.default;
  return p;
}

// Distinct, colour-blind-friendly palette for runs (works on dark background).
export const RUN_COLORS = ["#22d3ee", "#f59e0b", "#a78bfa", "#34d399", "#f472b6", "#60a5fa", "#fb7185", "#facc15", "#2dd4bf", "#c084fc"];

export const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
