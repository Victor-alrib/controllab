"""Declarative parameter specifications.

Every plant and controller declares its parameters with ``ParamSpec``. The same
specification is used to (1) validate/coerce incoming JSON and (2) let the
frontend render the configuration forms automatically. Adding a new model
therefore requires no frontend change.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

import numpy as np

ParamKind = Literal["float", "int", "bool", "select", "vector", "matrix"]


class ParamError(ValueError):
    """Raised when a user supplied parameter is invalid (mapped to HTTP 422)."""


@dataclass
class ParamSpec:
    key: str
    label: str
    kind: ParamKind = "float"
    default: Any = None
    unit: str = ""
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[dict[str, str]] | None = None
    description: str = ""
    group: str = "Parâmetros"
    advanced: bool = False
    # Exclusive lower bound (e.g. a time constant must be strictly positive).
    exclusive_min: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _check_bounds(spec: ParamSpec, value: float) -> None:
    if not np.isfinite(value):
        raise ParamError(f"'{spec.label}' deve ser um número finito.")
    if spec.min is not None:
        if spec.exclusive_min and value <= spec.min:
            raise ParamError(f"'{spec.label}' deve ser > {spec.min}.")
        if not spec.exclusive_min and value < spec.min:
            raise ParamError(f"'{spec.label}' deve ser ≥ {spec.min}.")
    if spec.max is not None and value > spec.max:
        raise ParamError(f"'{spec.label}' deve ser ≤ {spec.max}.")


def _to_float(spec: ParamSpec, raw: Any) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ParamError(f"'{spec.label}' deve ser numérico (recebido: {raw!r}).") from None


def coerce_params(specs: list[ParamSpec], raw: dict[str, Any] | None) -> dict[str, Any]:
    """Validate ``raw`` against ``specs`` filling defaults for missing keys."""
    raw = dict(raw or {})
    out: dict[str, Any] = {}
    for spec in specs:
        value = raw.get(spec.key, spec.default)
        if value is None:
            raise ParamError(f"Parâmetro obrigatório ausente: '{spec.label}'.")
        if spec.kind == "float":
            v = _to_float(spec, value)
            _check_bounds(spec, v)
            out[spec.key] = v
        elif spec.kind == "int":
            v = _to_float(spec, value)
            if v != int(v):
                raise ParamError(f"'{spec.label}' deve ser inteiro.")
            _check_bounds(spec, v)
            out[spec.key] = int(v)
        elif spec.kind == "bool":
            out[spec.key] = bool(value)
        elif spec.kind == "select":
            allowed = [o["value"] for o in (spec.options or [])]
            if value not in allowed:
                raise ParamError(f"'{spec.label}' deve ser um de {allowed}.")
            out[spec.key] = value
        elif spec.kind == "vector":
            try:
                arr = np.asarray(value, dtype=float).reshape(-1)
            except (TypeError, ValueError):
                raise ParamError(f"'{spec.label}' deve ser uma lista de números.") from None
            if not np.all(np.isfinite(arr)):
                raise ParamError(f"'{spec.label}' contém valores não finitos.")
            out[spec.key] = arr
        elif spec.kind == "matrix":
            try:
                arr = np.atleast_2d(np.asarray(value, dtype=float))
            except (TypeError, ValueError):
                raise ParamError(
                    f"'{spec.label}' deve ser uma matriz (lista de linhas de mesmo tamanho)."
                ) from None
            if arr.ndim != 2 or not np.all(np.isfinite(arr)):
                raise ParamError(f"'{spec.label}' deve ser uma matriz numérica finita.")
            out[spec.key] = arr
        else:  # pragma: no cover - guarded by Literal
            raise ParamError(f"Tipo de parâmetro desconhecido: {spec.kind}")
    return out


def jsonable(value: Any) -> Any:
    """Convert numpy containers into JSON serialisable Python objects."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


__all__ = ["ParamSpec", "ParamError", "coerce_params", "jsonable", "field"]
