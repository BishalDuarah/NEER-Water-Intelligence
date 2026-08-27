"""Measurement generation: normal baseline behavior and incident perturbation.

Normal generation is deterministic given a seeded `random.Random`. Incident
perturbation is applied *after* generation as a pure transformation, so a
scenario only ever rewrites measurements for its target zone. This gives the
intelligence layer a clean property: turning a scenario on changes exactly one
zone and leaves every other zone bit-identical.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Iterator

from app.simulation.config import MetricProfile, SimulationConfig, ZoneProfiles
from app.simulation.models import CitizenReport, Measurement
from app.simulation.scenarios import IncidentSpec

REPORT_TEMPLATES: dict[str, str] = {
    "low_pressure": "Resident reports very low water pressure at the tap.",
    "supply_disruption": "Resident reports complete water supply interruption.",
}

REPORT_SEVERITY: dict[str, str] = {
    "low_pressure": "moderate",
    "supply_disruption": "high",
}


def make_rng(seed: int, tag: str) -> random.Random:
    """Derive an independent, deterministic RNG from seed + tag."""
    return random.Random(f"{seed}:{tag}")


def number_of_steps(config: SimulationConfig) -> int:
    if config.interval_minutes <= 0:
        raise ValueError(f"interval_minutes must be positive, got {config.interval_minutes}")
    if config.duration_hours <= 0:
        raise ValueError(f"duration_hours must be positive, got {config.duration_hours}")
    steps = int((config.duration_hours * 60.0) / config.interval_minutes)
    if steps < 1:
        raise ValueError("time window is shorter than one interval; nothing to simulate")
    return steps


def iter_timestamps(config: SimulationConfig) -> Iterator[datetime]:
    """Yield measurement timestamps across the configured time window."""
    step = timedelta(minutes=config.interval_minutes)
    current = config.start_time
    for _ in range(number_of_steps(config)):
        yield current
        current += step


def diurnal_factor(hour: float) -> float:
    """Smooth daily demand pattern (~0.78 .. ~0.96): night trough, lunch and
    evening peaks. A deterministic pure function of the hour."""
    midday = 0.18 * math.exp(-(((hour - 11.5) / 4.0) ** 2))
    evening = 0.14 * math.exp(-(((hour - 19.5) / 4.0) ** 2))
    return 0.78 + midday + evening


def _clamp(value: float, profile: MetricProfile) -> float:
    return min(max(value, profile.min_value), profile.max_value)


def generate_normal_zone(
    zone_id: str,
    profiles: ZoneProfiles,
    config: SimulationConfig,
    rng: random.Random,
) -> list[Measurement]:
    """Generate normal (baseline) measurements for one zone across the window."""
    measurements: list[Measurement] = []
    for ts in iter_timestamps(config):
        demand = diurnal_factor(ts.hour + ts.minute / 60.0) if config.diurnal_enabled else 1.0

        flow_value = _clamp(
            profiles.flow.baseline * demand + rng.gauss(0.0, profiles.flow.sigma),
            profiles.flow,
        )
        # Pressure edges slightly *down* as demand rises.
        pressure_value = _clamp(
            profiles.pressure.baseline * (1.0 + 0.05 * (1.0 - demand))
            + rng.gauss(0.0, profiles.pressure.sigma),
            profiles.pressure,
        )
        quality_value = _clamp(
            profiles.quality.baseline + rng.gauss(0.0, profiles.quality.sigma),
            profiles.quality,
        )
        consumption_value = _clamp(
            profiles.consumption.baseline * demand
            + rng.gauss(0.0, profiles.consumption.sigma),
            profiles.consumption,
        )

        measurements.extend(
            [
                Measurement(ts, zone_id, "flow", flow_value, profiles.flow.unit),
                Measurement(ts, zone_id, "pressure", pressure_value, profiles.pressure.unit),
                Measurement(ts, zone_id, "quality", quality_value, profiles.quality.unit),
                Measurement(ts, zone_id, "consumption", consumption_value, profiles.consumption.unit),
            ]
        )
    return measurements


def incident_window(config: SimulationConfig, spec: IncidentSpec) -> tuple[datetime, datetime]:
    """Absolute window in which the scenario is active."""
    start = config.start_time + timedelta(minutes=spec.start_offset_minutes)
    return start, start + timedelta(minutes=spec.duration_minutes)


def _profile_for(profiles: ZoneProfiles, metric: str) -> MetricProfile:
    return getattr(profiles, metric)


def apply_incident(
    measurements: list[Measurement],
    spec: IncidentSpec,
    config: SimulationConfig,
    rng: random.Random,
) -> list[Measurement]:
    """Rewrite the target zone's in-window measurements per the scenario.

    Outside the window, and for all other zones, measurements pass through
    unchanged (same objects, no new draws) so they stay bit-identical.
    """
    if spec.zone_id not in config.profiles:
        raise ValueError(f"scenario {spec.id}: unknown zone {spec.zone_id!r}")
    profiles = config.profiles[spec.zone_id]
    win_start, win_end = incident_window(config, spec)
    ramp_minutes = max(float(config.incident_ramp_minutes), 1e-9)

    out: list[Measurement] = []
    for m in measurements:
        if m.zone_id != spec.zone_id or not (win_start <= m.timestamp < win_end):
            out.append(m)
            continue
        elapsed_min = (m.timestamp - win_start).total_seconds() / 60.0
        ramp = min(1.0, elapsed_min / ramp_minutes)
        factor = spec.factors.get(m.metric, 1.0)
        multiplier = 1.0 + (factor - 1.0) * ramp
        noise = 1.0 + rng.gauss(0.0, spec.noise_fraction * spec.noise_multiplier)
        value = _clamp(m.value * multiplier * noise, _profile_for(profiles, m.metric))
        out.append(Measurement(m.timestamp, m.zone_id, m.metric, value, m.unit))
    return out


def generate_citizen_reports(
    spec: IncidentSpec,
    win_start: datetime,
    win_end: datetime,
    config: SimulationConfig,
    rng: random.Random,
) -> list[CitizenReport]:
    """Generate deterministic citizen reports spread across the incident window."""
    if config.citizen_reports_per_scenario < 1:
        return []
    width_min = int((win_end - win_start).total_seconds() // 60)
    reports: list[CitizenReport] = []
    for i in range(config.citizen_reports_per_scenario):
        offset_min = rng.randrange(0, width_min)
        timestamp = win_start + timedelta(minutes=offset_min)
        category = rng.choice(config.incident_report_categories)
        severity = REPORT_SEVERITY.get(category, "moderate")
        description = REPORT_TEMPLATES.get(category, f"{category} issue reported.")
        reports.append(
            CitizenReport(
                report_id=f"CR-{spec.zone_id}-{i + 1:04d}",
                zone_id=spec.zone_id,
                timestamp=timestamp,
                category=category,
                description=description,
                severity=severity,
                status="open",
            )
        )
    reports.sort(key=lambda r: (r.timestamp, r.report_id))
    return reports