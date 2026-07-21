from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SensorSpec:
    label: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = "measurement"
    precision: int | None = None
    icon: str | None = None


SENSOR_SPECS: dict[str, SensorSpec] = {
    "voltage": SensorSpec("Voltage", "V", "voltage", precision=1),
    "current": SensorSpec("Current", "A", "current", precision=3),
    "peakCurrent": SensorSpec("Peak current", "A", "current", precision=3),
    "maximumCurrent": SensorSpec("Maximum current", "A", "current", precision=3),
    "residualCurrent": SensorSpec("Residual current", "A", "current", precision=3),
    "residualACCurrent": SensorSpec("Residual AC current", "A", "current", precision=3),
    "residualDCCurrent": SensorSpec("Residual DC current", "A", "current", precision=3),
    "unbalancedCurrent": SensorSpec("Current unbalance", "%", precision=1),
    "activePower": SensorSpec("Active power", "W", "power", precision=1),
    "reactivePower": SensorSpec("Reactive power", "var", "reactive_power", precision=1),
    "apparentPower": SensorSpec("Apparent power", "VA", "apparent_power", precision=1),
    "powerFactor": SensorSpec("Power factor", None, "power_factor", precision=2),
    "displacementPowerFactor": SensorSpec("Displacement power factor", None, "power_factor", precision=2),
    "activeEnergy": SensorSpec("Active energy", "Wh", "energy", "total_increasing", 3),
    "apparentEnergy": SensorSpec("Apparent energy", "VAh", None, "total_increasing", 3),
    "phaseAngle": SensorSpec("Phase angle", "°", precision=1),
    "lineFrequency": SensorSpec("Frequency", "Hz", "frequency", precision=1),
    "crestFactor": SensorSpec("Crest factor", precision=2),
    "voltageThd": SensorSpec("Voltage THD", "%", precision=1),
    "currentThd": SensorSpec("Current THD", "%", precision=1),
    "inrushCurrent": SensorSpec("Inrush current", "A", "current", precision=3),
}


@dataclass
class SensorBinding:
    scope: str
    index: int
    attribute: str
    sensor: Any
    spec: SensorSpec
    state_topic: str = ""
    state_key: str = ""


@dataclass
class OutletBinding:
    index: int
    outlet: Any
    label: str
    name: str
    switchable: bool
    state_topic: str
    command_topic: str
    cycle_topic: str


def sanitize(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return text.strip("_").lower() or "unknown"


def safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    return default if value is None else value


def reading_value(reading: Any, spec: SensorSpec) -> float | int | None:
    if not bool(safe_attr(reading, "available", False)) or not bool(safe_attr(reading, "valid", False)):
        return None
    try:
        numeric = float(safe_attr(reading, "value"))
    except (TypeError, ValueError):
        return None
    if spec.precision is not None:
        numeric = round(numeric, spec.precision)
    return int(numeric) if numeric.is_integer() and spec.precision == 0 else numeric


def datetime_value(value: Any) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
