"""ControlLab API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.analysis.linear import analyze
from app.controllers.registry import controller_catalog
from app.core.params import ParamError
from app.plants.registry import plant_catalog
from app.report.html_report import build_report
from app.schemas import ReportRequest, SimulationRequest
from app.simulation.engine import result_to_csv, result_to_json, simulate

app = FastAPI(title="ControlLab API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.exception_handler(ParamError)
async def _param_error(_: Request, exc: ParamError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/catalog")
def catalog():
    return {"plants": plant_catalog(), "controllers": controller_catalog()}


@app.post("/api/simulate")
def run_simulation(req: SimulationRequest):
    res = simulate(req)
    return result_to_json(res, req.settings.max_plot_points)


@app.post("/api/analyze")
def run_analysis(req: SimulationRequest):
    return analyze(req)


@app.post("/api/export/csv", response_class=PlainTextResponse)
def export_csv(req: SimulationRequest):
    res = simulate(req)
    return PlainTextResponse(
        result_to_csv(res), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=controllab.csv"},
    )


@app.post("/api/report", response_class=HTMLResponse)
def report(req: ReportRequest):
    return HTMLResponse(build_report(req))


# Serve the built frontend (production / single-process mode) if present.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = _DIST / path
        return FileResponse(f if path and f.is_file() else _DIST / "index.html")
