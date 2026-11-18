"""API request schemas (pydantic)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ModelConfig(BaseModel):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)


class ReferenceConfig(BaseModel):
    type: Literal["step", "ramp", "sine", "square", "constant"] = "step"
    amplitude: float = 1.0
    initial: float = 0.0          # value before the step / offset of other signals
    time: float = Field(0.0, ge=0)  # step instant / start time
    slope: float = 1.0            # ramp slope
    frequency: float = Field(0.2, gt=0)  # Hz (sine, square)


class DisturbanceConfig(BaseModel):
    enabled: bool = True
    target: Literal["input", "output"] = "input"
    shape: Literal["step", "pulse", "sine"] = "step"
    amplitude: float = 0.5
    time: float = Field(5.0, ge=0)
    duration: float = Field(1.0, gt=0)   # pulse width
    frequency: float = Field(1.0, gt=0)  # Hz (sine)


class NoiseConfig(BaseModel):
    enabled: bool = False
    std: float = Field(0.01, ge=0)
    seed: int = 0


class SaturationConfig(BaseModel):
    enabled: bool = False
    u_min: float = -10.0
    u_max: float = 10.0

    @model_validator(mode="after")
    def _order(self):
        if self.enabled and self.u_min >= self.u_max:
            raise ValueError("Saturação: u_min deve ser menor que u_max.")
        return self


class SimulationSettings(BaseModel):
    t_final: float = Field(10.0, gt=0, le=1e5)
    Ts: float = Field(0.01, gt=0)
    settling_band: float = Field(0.02, gt=0, lt=0.5)
    max_plot_points: int = Field(6000, ge=200, le=200000)


class SimulationRequest(BaseModel):
    plant: ModelConfig = ModelConfig(type="second_order")
    controller: ModelConfig = ModelConfig(type="pid")
    reference: ReferenceConfig = ReferenceConfig()
    disturbances: list[DisturbanceConfig] = Field(default_factory=list)
    noise: NoiseConfig = NoiseConfig()
    saturation: SaturationConfig = SaturationConfig()
    settings: SimulationSettings = SimulationSettings()


class ReportRun(BaseModel):
    label: str
    config: SimulationRequest


class ReportRequest(BaseModel):
    title: str = "Relatório ControlLab"
    author: str = ""
    notes: str = ""
    runs: list[ReportRun] = Field(min_length=1, max_length=10)
