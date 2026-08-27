"""Phase 4-B1 API schemas for the read-only telemetry endpoint.

These Pydantic models are the HTTP boundary of ``POST /api/v1/telemetry/run``.
They wrap the deterministic ``SimulationResult`` projections produced by the
simulator into a compact, JSON-safe shape. Each measurement exposes exactly the
fields of the deterministic ``Measurement`` model (timestamp, zone_id, metric,
value, unit) — nothing is interpolated, derived, or reconstructed. Zones and
scenario outcomes mirror the ``Zone`` / ``ScenarioOutcome`` models verbatim.

This boundary intentionally contains no anomaly, correlation, risk, or AI
fields: telemetry is simulation output only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TelemetryRunRequest(BaseModel):
    """Control parameters for one deterministic telemetry run.

    These are the same simulation inputs the analysis endpoint accepts (minus
    ``reference_seed``, which only controls the separate 7-day reference window
    used for anomaly scoring and never changes the simulated measurements).
    """

    seed: int = Field(default=42, ge=0, le=100_000, description="Simulation random seed.")
    days: float = Field(
        default=1.0,
        gt=0,
        le=30.0,
        description="Number of simulated days of measurements (fractional allowed).",
    )
    scenario: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Registered simulation scenario id (e.g. ZONE_B_SUPPLY_INCIDENT).",
    )


class TelemetryZone(BaseModel):
    """A simulated supply zone (exact projection of the deterministic Zone)."""

    zone_id: str
    name: str
    district: str
    area_sq_km: float
    estimated_population: int


class TelemetryMeasurement(BaseModel):
    """One timestamped sensor reading (exact ``Measurement`` projection)."""

    timestamp: datetime
    zone_id: str
    metric: str  # flow | pressure | quality | consumption
    value: float
    unit: str


class TelemetryScenario(BaseModel):
    """Which scenario ran, where, and when (exact ``ScenarioOutcome`` projection)."""

    scenario_id: str
    zone_id: str
    window_start: datetime
    window_end: datetime
    description: str


class TelemetryRunMetadata(BaseModel):
    """Metadata about a single telemetry run."""

    run_id: str
    seed: int
    days: float
    scenario: str | None
    data_source: Literal["deterministic-simulation"] = "deterministic-simulation"
    window_hours: float
    zone_count: int
    measurement_count: int
    ran_at: datetime


class TelemetryRunResponse(BaseModel):
    """Response of ``POST /api/v1/telemetry/run``."""

    run: TelemetryRunMetadata
    zones: list[TelemetryZone]
    measurements: list[TelemetryMeasurement]
    scenarios: list[TelemetryScenario]