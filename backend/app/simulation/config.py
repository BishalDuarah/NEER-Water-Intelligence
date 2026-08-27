"""Simulation configuration.

Every tunable knob of the water-network simulator lives here: baselines,
acceptable ranges, natural variation, incident windows, number of zones, time
window, and random seed. Centralizing the knobs keeps generated measurements
reproducible and auditable; simulation logic does not scatter magic numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# Fixed UTC anchor so windows are well-defined and reproducible.
START_TIME_DEFAULT = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# Units are part of every MetricProfile (explicit units in the data model).
METRIC_NAMES: tuple[str, ...] = ("flow", "pressure", "quality", "consumption")


@dataclass(frozen=True)
class MetricProfile:
    """Baseline + acceptable range + natural-variation spread for one metric."""

    unit: str
    baseline: float
    min_value: float
    max_value: float
    sigma: float  # std. dev. of the normal noise around the current mean


@dataclass(frozen=True)
class ZoneProfiles:
    """All metric profiles for a single zone."""

    flow: MetricProfile
    pressure: MetricProfile
    quality: MetricProfile
    consumption: MetricProfile


# (flow, pressure, quality, consumption) baselines at a demand factor of 1.0
# per zone. Units: m3/h, bar, mg/L chlorine residual, m3/h.
_ZONE_BASELINES: dict[str, tuple[float, float, float, float]] = {
    "A": (5200.0, 4.20, 0.50, 4680.0),
    "B": (3100.0, 4.00, 0.50, 2790.0),
    "C": (1500.0, 4.40, 0.50, 1350.0),
    "D": (4800.0, 4.10, 0.48, 4320.0),
}


def _flow_profile(baseline: float) -> MetricProfile:
    return MetricProfile(
        unit="m3/h",
        baseline=baseline,
        min_value=0.5 * baseline,
        max_value=1.6 * baseline,
        sigma=0.03 * baseline,
    )


def _pressure_profile(baseline: float) -> MetricProfile:
    return MetricProfile(
        unit="bar",
        baseline=baseline,
        min_value=2.0,
        max_value=6.0,
        sigma=0.06,
    )


def _quality_profile(baseline: float) -> MetricProfile:
    return MetricProfile(
        unit="mg/L",
        baseline=baseline,
        min_value=0.10,
        max_value=1.20,
        sigma=0.02,
    )


def _consumption_profile(baseline: float) -> MetricProfile:
    return MetricProfile(
        unit="m3/h",
        baseline=baseline,
        min_value=0.5 * baseline,
        max_value=1.6 * baseline,
        sigma=0.03 * baseline,
    )


def _build_profiles() -> dict[str, ZoneProfiles]:
    profiles: dict[str, ZoneProfiles] = {}
    for zone_id, (flow_b, pressure_b, quality_b, consumption_b) in _ZONE_BASELINES.items():
        profiles[zone_id] = ZoneProfiles(
            flow=_flow_profile(flow_b),
            pressure=_pressure_profile(pressure_b),
            quality=_quality_profile(quality_b),
            consumption=_consumption_profile(consumption_b),
        )
    return profiles


@dataclass(frozen=True)
class SimulationConfig:
    """Fully specified, deterministic simulation schedule."""

    seed: int = 42
    start_time: datetime = START_TIME_DEFAULT
    interval_minutes: int = 15
    duration_hours: float = 24.0
    zone_ids: tuple[str, ...] = ("A", "B", "C", "D")
    scenario_ids: tuple[str, ...] = ()
    citizen_reports_per_scenario: int = 12
    incident_report_categories: tuple[str, ...] = ("low_pressure", "supply_disruption")
    incident_ramp_minutes: int = 30
    diurnal_enabled: bool = True
    profiles: dict[str, ZoneProfiles] = field(default_factory=_build_profiles)


def build_config(**overrides: object) -> SimulationConfig:
    """Build a SimulationConfig, optionally overriding defaults by keyword."""
    return SimulationConfig(**overrides)


def default_config() -> SimulationConfig:
    """The default config: 4 zones, 24 h at 15 min, no scenarios, seed 42."""
    return SimulationConfig()