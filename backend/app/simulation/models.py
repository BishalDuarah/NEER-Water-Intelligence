"""Core data structures produced by the water-network simulator.

These are plain frozen dataclasses on purpose: they are independent of the
database, FastAPI, and any AI/numerical stack, so the intelligence layer can
consume them directly. Dedicated adapters (Pydantic schemas, SQLAlchemy models)
can map them later without touching the simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.simulation.config import SimulationConfig


@dataclass(frozen=True)
class Zone:
    """A water-supply zone in the simulated network."""

    zone_id: str
    name: str
    district: str
    area_sq_km: float
    estimated_population: int


@dataclass(frozen=True)
class Measurement:
    """A single timestamped sensor reading for one zone and one metric."""

    timestamp: datetime
    zone_id: str
    metric: str  # flow | pressure | quality | consumption
    value: float
    unit: str


@dataclass(frozen=True)
class CitizenReport:
    """A simulated citizen contact (complaint/notification) for a zone."""

    report_id: str
    zone_id: str
    timestamp: datetime
    category: str
    description: str
    severity: str  # low | moderate | high
    status: str  # open until an operator resolves it


@dataclass(frozen=True)
class ScenarioOutcome:
    """Record of which scenario ran, where, and when."""

    scenario_id: str
    zone_id: str
    window_start: datetime
    window_end: datetime
    description: str


@dataclass
class SimulationResult:
    """Everything produced by a single deterministic simulation run."""

    config: SimulationConfig
    zones: list[Zone]
    measurements: list[Measurement]
    reports: list[CitizenReport]
    scenarios: list[ScenarioOutcome]