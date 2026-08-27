"""Phase 1 tests: water-network simulation (data generation only)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.simulation import (
    SCENARIOS,
    ZONE_B_SUPPLY_INCIDENT,
    build_config,
    run_simulation,
)
from app.simulation.config import SimulationConfig
from app.simulation.generator import incident_window
from app.simulation.models import SimulationResult


def _config(scenario: bool = False, seed: int = 42, **overrides: object) -> SimulationConfig:
    cfg = build_config(
        seed=seed,
        scenario_ids=("ZONE_B_SUPPLY_INCIDENT",) if scenario else (),
    )
    return replace(cfg, **overrides)  # type: ignore[arg-type]


def _mean_in_window(result: SimulationResult, zone_id: str, metric: str, start, end) -> float:
    values = [
        m.value
        for m in result.measurements
        if m.zone_id == zone_id and m.metric == metric and start <= m.timestamp < end
    ]
    assert values, f"no {metric} measurements for zone {zone_id} in the window"
    return sum(values) / len(values)


def test_four_zones_are_generated() -> None:
    result = run_simulation(_config())
    assert [z.zone_id for z in result.zones] == ["A", "B", "C", "D"]
    assert all(z.estimated_population > 0 for z in result.zones)
    assert all(z.name and z.district for z in result.zones)


def test_measurements_have_valid_timestamps_and_zone_ids() -> None:
    cfg = build_config()
    result = run_simulation(cfg)
    zone_ids = {z.zone_id for z in result.zones}
    window_end = cfg.start_time + timedelta(minutes=int(cfg.duration_hours * 60))

    assert result.measurements
    for m in result.measurements:
        assert m.zone_id in zone_ids
        assert m.timestamp.tzinfo is not None
        assert cfg.start_time <= m.timestamp < window_end
        assert m.unit
        assert m.metric in {"flow", "pressure", "quality", "consumption"}

    metrics = {m.metric for m in result.measurements}
    assert metrics == {"flow", "pressure", "quality", "consumption"}


def test_normal_simulation_stays_within_configured_ranges() -> None:
    cfg = build_config()
    result = run_simulation(cfg)
    for zone in result.zones:
        profiles = cfg.profiles[zone.zone_id]
        for m in (m for m in result.measurements if m.zone_id == zone.zone_id):
            profile = getattr(profiles, m.metric)
            assert profile.min_value <= m.value <= profile.max_value, (
                f"zone {zone.zone_id} {m.metric} {m.value} out of "
                f"[{profile.min_value}, {profile.max_value}]"
            )


def test_fixed_seed_produces_reproducible_results() -> None:
    first = run_simulation(_config(scenario=True))
    second = run_simulation(_config(scenario=True))
    assert first.measurements == second.measurements
    assert first.reports == second.reports


def test_zone_b_incident_changes_zone_b_measurements() -> None:
    incident = run_simulation(_config(scenario=True))
    normal = run_simulation(_config(scenario=False))
    start, end = incident_window(incident.config, ZONE_B_SUPPLY_INCIDENT)

    normal_pressure = _mean_in_window(normal, "B", "pressure", start, end)
    incident_pressure = _mean_in_window(incident, "B", "pressure", start, end)
    assert incident_pressure < 0.75 * normal_pressure

    normal_flow = _mean_in_window(normal, "B", "flow", start, end)
    incident_flow = _mean_in_window(incident, "B", "flow", start, end)
    assert incident_flow > 1.1 * normal_flow

    normal_consumption = _mean_in_window(normal, "B", "consumption", start, end)
    incident_consumption = _mean_in_window(incident, "B", "consumption", start, end)
    assert incident_consumption < 0.85 * normal_consumption

    normal_quality = _mean_in_window(normal, "B", "quality", start, end)
    incident_quality = _mean_in_window(incident, "B", "quality", start, end)
    assert incident_quality < normal_quality


def test_incident_does_not_modify_unrelated_zones() -> None:
    normal = run_simulation(_config(scenario=False))
    incident = run_simulation(_config(scenario=True))

    for zone_id in ("A", "C", "D"):
        normal_zone = [m for m in normal.measurements if m.zone_id == zone_id]
        incident_zone = [m for m in incident.measurements if m.zone_id == zone_id]
        assert normal_zone == incident_zone, f"zone {zone_id} was modified by the scenario"


def test_citizen_reports_generated_for_incident_scenario() -> None:
    incident = run_simulation(_config(scenario=True))
    assert incident.reports
    assert len(incident.reports) == incident.config.citizen_reports_per_scenario

    start, end = incident_window(incident.config, ZONE_B_SUPPLY_INCIDENT)
    for report in incident.reports:
        assert report.zone_id == "B"
        assert start <= report.timestamp < end
        assert report.category in incident.config.incident_report_categories
        assert report.severity in {"low", "moderate", "high"}
        assert report.status == "open"
        assert report.report_id.startswith("CR-B-")


def test_normal_run_has_no_citizen_reports() -> None:
    result = run_simulation(_config(scenario=False))
    assert result.reports == []
    assert result.scenarios == []


def test_unknown_scenario_raises() -> None:
    with pytest.raises(ValueError, match="Unknown scenario"):
        run_simulation(replace(build_config(), scenario_ids=("NOT_A_SCENARIO",)))

def test_scenario_registry_contains_zone_b_incident() -> None:
    assert "ZONE_B_SUPPLY_INCIDENT" in SCENARIOS
    spec = SCENARIOS["ZONE_B_SUPPLY_INCIDENT"]
    assert spec.zone_id == "B"
    assert spec.factors["pressure"] < 1.0
    assert spec.factors["flow"] > 1.0
    assert spec.factors["consumption"] < 1.0
    assert spec.duration_minutes > 0