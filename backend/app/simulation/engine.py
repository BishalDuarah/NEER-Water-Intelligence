"""Simulation orchestrator.

`run_simulation` is the single entry point: it validates the config, generates
normal measurements for every zone, applies each active scenario, and emits the
structured result (zones, measurements, citizen reports, scenario outcomes).
The orchestrator performs no database or API work, so it stays independently
testable and database-agnostic.
"""

from __future__ import annotations

from app.simulation.config import SimulationConfig
from app.simulation.generator import (
    apply_incident,
    generate_citizen_reports,
    generate_normal_zone,
    incident_window,
    make_rng,
)
from app.simulation.models import CitizenReport, Measurement, ScenarioOutcome, SimulationResult, Zone
from app.simulation.scenarios import SCENARIOS
from app.simulation.zones import ZONES


def run_simulation(config: SimulationConfig) -> SimulationResult:
    _validate(config)

    zone_map: dict[str, Zone] = {z.zone_id: z for z in ZONES}
    zones: list[Zone] = [zone_map[zone_id] for zone_id in config.zone_ids]

    measurements: list[Measurement] = []
    for zone in zones:
        rng = make_rng(config.seed, f"zone:{zone.zone_id}")
        measurements.extend(
            generate_normal_zone(zone.zone_id, config.profiles[zone.zone_id], config, rng)
        )

    scenario_outcomes: list[ScenarioOutcome] = []
    reports: list[CitizenReport] = []
    for scenario_id in config.scenario_ids:
        spec = SCENARIOS[scenario_id]
        rng = make_rng(config.seed, f"scenario:{scenario_id}")
        win_start, win_end = incident_window(config, spec)
        measurements = apply_incident(measurements, spec, config, rng)
        scenario_outcomes.append(
            ScenarioOutcome(
                scenario_id=scenario_id,
                zone_id=spec.zone_id,
                window_start=win_start,
                window_end=win_end,
                description=spec.description,
            )
        )
        reports.extend(generate_citizen_reports(spec, win_start, win_end, config, rng))

    reports.sort(key=lambda r: (r.timestamp, r.report_id))
    return SimulationResult(
        config=config,
        zones=zones,
        measurements=measurements,
        reports=reports,
        scenarios=scenario_outcomes,
    )


def _validate(config: SimulationConfig) -> None:
    if not config.zone_ids:
        raise ValueError("Simulation requires at least one zone.")
    known_zones = {z.zone_id for z in ZONES}
    unknown_zones = sorted(set(config.zone_ids) - known_zones)
    if unknown_zones:
        raise ValueError(f"Unknown zone ids: {unknown_zones}")

    unknown_scenarios = sorted(set(config.scenario_ids) - set(SCENARIOS))
    if unknown_scenarios:
        raise ValueError(f"Unknown scenario ids: {unknown_scenarios}")