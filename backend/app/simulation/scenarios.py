"""Incident scenarios.

A scenario is a declarative `IncidentSpec`: which zone is affected, when the
window starts (offset from simulation start) and how long it lasts, and what
per-metric multiplier is applied. Multipliers are ramped in over
`incident_ramp_minutes` to avoid an unrealistic hard step. New scenarios are
added by defining another `IncidentSpec` and registering it in `SCENARIOS`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncidentSpec:
    """Declarative description of a reproducible incident scenario."""

    id: str
    zone_id: str
    start_offset_minutes: int  # from simulation start_time
    duration_minutes: int
    description: str
    # metric -> multiplier (ramped from 1.0 to the factor over the ramp window)
    factors: dict[str, float]
    # extra noise: value * gauss(0, noise_fraction * noise_multiplier)
    noise_fraction: float = 0.01
    noise_multiplier: float = 3.0


ZONE_B_SUPPLY_INCIDENT: IncidentSpec = IncidentSpec(
    id="ZONE_B_SUPPLY_INCIDENT",
    zone_id="B",
    start_offset_minutes=360,  # 06:00 UTC
    duration_minutes=360,  # 6 hours -> ends 12:00 UTC
    description=(
        "Supply disruption in Zone B: pressure drops to ~50%, inflow flow "
        "rises to ~125% (lost water), usable consumption drops to ~60%, and "
        "citizens file low-pressure / supply-disruption reports."
    ),
    factors={"pressure": 0.50, "flow": 1.25, "consumption": 0.60, "quality": 0.85},
)

SCENARIOS: dict[str, IncidentSpec] = {
    ZONE_B_SUPPLY_INCIDENT.id: ZONE_B_SUPPLY_INCIDENT,
}