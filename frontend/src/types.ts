// Types mirroring the backend API (app/schemas.py and catalog descriptors).

export type ParamKind = "float" | "int" | "bool" | "select" | "vector" | "matrix";

export interface ParamSpec {
  key: string;
  label: string;
  kind: ParamKind;
  default: unknown;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];
  description?: string;
  group: string;
  advanced: boolean;
  exclusive_min?: boolean;
}

export interface ModelDescriptor {
  type: string;
  name: string;
  description: string;
  equation: string;
  params: ParamSpec[];
  status?: "available" | "planned";
  requires_state?: boolean;
  is_linear?: boolean;
}

export interface Catalog {
  plants: ModelDescriptor[];
  controllers: ModelDescriptor[];
}

export type Params = Record<string, unknown>;

export interface ModelConfig {
  type: string;
  params: Params;
}

export interface ReferenceConfig {
  type: "step" | "ramp" | "sine" | "square" | "constant";
  amplitude: number;
  initial: number;
  time: number;
  slope: number;
  frequency: number;
}

export interface DisturbanceConfig {
  enabled: boolean;
  target: "input" | "output";
  shape: "step" | "pulse" | "sine";
  amplitude: number;
  time: number;
  duration: number;
  frequency: number;
}

export interface SimConfig {
  plant: ModelConfig;
  controller: ModelConfig;
  reference: ReferenceConfig;
  disturbances: DisturbanceConfig[];
  noise: { enabled: boolean; std: number; seed: number };
  saturation: { enabled: boolean; u_min: number; u_max: number };
  settings: { t_final: number; Ts: number; settling_band: number; max_plot_points: number };
}

type Series = (number | null)[];

export interface Metrics {
  overshoot_pct?: number | null;
  peak_value?: number | null;
  peak_time?: number | null;
  rise_time?: number | null;
  settling_time?: number | null;
  steady_state_error?: number | null;
  final_value?: number | null;
  settled?: boolean;
  final_error?: number;
  step_window_end?: number;
  IAE?: number;
  ISE?: number;
  ITAE?: number;
  ITSE?: number;
  u_max_abs?: number;
  control_energy?: number;
  total_variation?: number;
  saturation_pct?: number;
  stable_run: boolean;
}

export interface SimResult {
  signals: { t: Series; r: Series; y: Series; e: Series; u: Series; u_cmd: Series; d_in: Series; d_out: Series };
  samples: { t: Series; r: Series; y_meas: Series; u: Series; u_cmd: Series };
  metrics: Metrics;
  meta: {
    n_samples: number; n_substeps: number; h: number; Ts: number; t_final: number;
    delay_effective: number; plant_order: number; integration: string;
    metrics_window_start: number; settling_band: number; reference_type: string;
    plotted_points: number; decimated: boolean;
  };
  warnings: string[];
}

export interface PoleInfo { re: number; im: number; wn: number | null; zeta: number | null; mag: number }

export interface Analysis {
  plant: {
    num: number[]; den: number[]; poles: PoleInfo[]; zeros: [number, number][];
    dc_gain: number | null; delay: number; stable: boolean;
  };
  plant_step: { t: number[]; y: (number | null)[] };
  controller?: { Cy_num: number[]; Cy_den: number[]; Cr_num: number[]; Cr_den: number[] };
  open_loop_freq?: { w: number[]; mag_db: (number | null)[]; phase_deg: number[] };
  margins?: {
    gain_margin_db: number | null; phase_margin_deg: number | null;
    w_phase_crossover: number | null; w_gain_crossover: number | null;
  };
  closed_loop: null | {
    continuous_poles: PoleInfo[]; continuous_stable: boolean;
    discrete_poles: PoleInfo[]; discrete_stable: boolean; spectral_radius: number;
  };
  notes: string[];
}

export interface Run {
  id: string;
  label: string;
  color: string;
  createdAt: number;
  config: SimConfig;
  metrics: Metrics;
  result?: SimResult; // not persisted; recomputed (deterministic) on demand
}
