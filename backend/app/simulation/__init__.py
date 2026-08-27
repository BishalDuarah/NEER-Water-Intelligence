"""NEER Water Intelligence - Phase 1 water-network simulation.

Phase 1 scope: realistic, reproducible data generation only. Anomaly
detection, correlation, risk scoring, classification, and the AI layer are
intentionally *not* here (later phases consume the output of this package).
"""

from app.simulation.config import (
    MetricProfile,
    SimulationConfig,
    ZoneProfiles,
    build_config,
    default_config,
)
from app.simulation.engine import run_simulation
from app.simulation.models import (
    CitizenReport,
    Measurement,
    ScenarioOutcome,
    SimulationResult,
    Zone,
)
from app.simulation.scenarios import SCENARIOS, ZONE_B_SUPPLY_INCIDENT
from app.simulation.zones import ZONES, ZONE_IDS

__all__ = [
    "CitizenReport",
    "Measurement",
    "MetricProfile",
    "SCENARIOS",
    "ScenarioOutcome",
    "SimulationConfig",
    "SimulationResult",
    "Zone",
    "ZoneProfiles",
    "ZONES",
    "ZONE_IDS",
    "ZONE_B_SUPPLY_INCIDENT",
    "build_config",
    "default_config",
    "run_simulation",
]