import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";
import type { Data, Layout } from "plotly.js";

const PlotlyComponent = createPlotlyComponent(Plotly);

export const C = {
  ref: "#94a3b8",
  y: "#22d3ee",
  e: "#f472b6",
  u: "#f59e0b",
  ucmd: "#f59e0b",
  meas: "#64748b",
  dist: "#a78bfa",
  grid: "#1c2530",
  axis: "#2a3644",
  text: "#8b9bab",
};

interface Props {
  data: Data[];
  title?: string;
  xTitle?: string;
  yTitle?: string;
  height?: number;
  layout?: Partial<Layout>;
  uirevision?: string;
}

export function Plot({ data, title, xTitle = "tempo [s]", yTitle, height = 260, layout, uirevision = "keep" }: Props) {
  const base: Partial<Layout> = {
    title: title ? { text: title, font: { size: 12, color: "#cbd5e1" }, x: 0.01, xanchor: "left", y: 0.97 } : undefined,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "#0a0f15",
    font: { family: "Inter, system-ui, sans-serif", size: 11, color: C.text },
    margin: { l: 56, r: 14, t: title ? 30 : 10, b: 40 },
    height,
    hovermode: "x unified",
    hoverlabel: { bgcolor: "#111821", bordercolor: "#2a3644", font: { family: "JetBrains Mono, ui-monospace, monospace", size: 11 } },
    showlegend: true,
    legend: { orientation: "h", x: 1, xanchor: "right", y: 1.02, yanchor: "bottom", font: { size: 10 }, bgcolor: "rgba(0,0,0,0)" },
    xaxis: {
      title: { text: xTitle, font: { size: 10 } }, gridcolor: C.grid, zerolinecolor: C.axis, linecolor: C.axis,
      tickfont: { family: "JetBrains Mono, ui-monospace, monospace", size: 10 },
    },
    yaxis: {
      title: { text: yTitle ?? "", font: { size: 10 } }, gridcolor: C.grid, zerolinecolor: C.axis, linecolor: C.axis,
      tickfont: { family: "JetBrains Mono, ui-monospace, monospace", size: 10 },
    },
    uirevision,
  };
  const merged: Partial<Layout> = {
    ...base,
    ...layout,
    xaxis: { ...base.xaxis, ...(layout?.xaxis ?? {}) },
    yaxis: { ...base.yaxis, ...(layout?.yaxis ?? {}) },
  };
  return (
    <PlotlyComponent
      data={data}
      layout={merged}
      config={{ displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d"], toImageButtonOptions: { format: "png", scale: 2 } }}
      style={{ width: "100%", height }}
      useResizeHandler
    />
  );
}
