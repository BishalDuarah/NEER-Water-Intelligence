"""Phase 4-B1 tests: FastAPI telemetry endpoint + service behavior.

Covers the API boundary and the deterministic guarantees demanded of the
read-only telemetry contract: endpoint exists, normal and golden runs return
real simulator output, zones/timestamps/units are authoritative, the run is
reproducible, scenarios perturb only the target zone (A/C/D stay bit-identical
to the normal run), validation returns 422, and no AI / database / simulation
internals are pulled into the response or the simulation package.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from statistics import fmean

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.simulation import SCENARIOS
from app.simulation.models import Measurement, SimulationResult
from app.simulation import build_config, run_simulation

NORMAL_REQUEST = {"seed": 42, "days": 1}
GOLDEN_REQUEST = {"seed": 42, "days": 1, "scenario": "ZONE_B_SUPPLY_INCIDENT"}

METRICS = ("flow", "pressure", "quality", "consumption")
UNITS = {"flow": "m3/h", "pressure": "bar", "quality": "mg/L", "consumption": "m3/h"}
ZONES_EXPECTED = {"A", "B", "C", "D"}

_MEASUREMENTS_PER_ZONE_DAY = 96  # 24 h / 15 min
_MEASUREMENTS_PER_DAY = _MEASUREMENTS_PER_ZONE_DAY * len(ZONES_EXPECTED) * len(METRICS)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _post(client: TestClient, payload: dict | None = None):
    if payload is None:
        return client.post("/api/v1/telemetry/run")
    return client.post("/api/v1/telemetry/run", json=payload)


def _by_key(measurements: list[dict]) -> dict[tuple[str, str, str], float]:
    """Map (timestamp iso string, zone, metric) -> value for easy comparison."""
    return {(m["timestamp"], m["zone_id"], m["metric"]): m["value"] for m in measurements}


def _zone_measurements(measurements: list[dict], zone_id: str) -> list[dict]:
    return [m for m in measurements if m["zone_id"] == zone_id]


def _window_means(measurements: list[dict], zone_id: str) -> dict[str, float]:
    """Mean per metric for a zone, split by the golden incident window."""
    window_start = datetime(2026, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    inside: dict[str, list[float]] = {m: [] for m in METRICS}
    outside_after: dict[str, list[float]] = {m: [] for m in METRICS}
    for m in measurements:
        if m["zone_id"] != zone_id:
            continue
        ts = _parse(m["timestamp"])
        target = inside if window_start <= ts < window_end else outside_after
        target[m["metric"]].append(m["value"])
    return {
        metric: (fmean(inside[metric]) - fmean(outside_after[metric]))
        for metric in METRICS
    }


# --- 1/18. endpoint existence and basic wiring ----------------------------------


def test_telemetry_endpoint_is_registered() -> None:
    paths = set(app.openapi()["paths"])
    assert "/api/v1/telemetry/run" in paths
    assert "post" in app.openapi()["paths"]["/api/v1/telemetry/run"]
    assert "/api/v1/analysis/run" in paths


def test_normal_run_returns_200_and_expected_shape(client: TestClient) -> None:
    body = _post(client, NORMAL_REQUEST).json()
    assert set(body) == {"run", "zones", "measurements", "scenarios"}
    assert body["run"]["data_source"] == "deterministic-simulation"
    assert body["run"]["seed"] == 42
    assert body["run"]["days"] == 1
    assert body["run"]["scenario"] is None
    assert body["run"]["zone_count"] == 4
    assert body["run"]["measurement_count"] == _MEASUREMENTS_PER_DAY
    assert body["run"]["window_hours"] == 24.0
    assert body["scenarios"] == []


def test_golden_zone_b_returns_telemetry(client: TestClient) -> None:
    body = _post(client, GOLDEN_REQUEST).json()
    assert body["run"]["scenario"] == "ZONE_B_SUPPLY_INCIDENT"
    assert body["run"]["measurement_count"] == _MEASUREMENTS_PER_DAY
    assert len(body["scenarios"]) == 1
    scenario = body["scenarios"][0]
    assert scenario["scenario_id"] == "ZONE_B_SUPPLY_INCIDENT"
    assert scenario["zone_id"] == "B"
    assert scenario["window_start"] == "2026-01-01T06:00:00Z"
    assert scenario["window_end"] == "2026-01-01T12:00:00Z"


# --- 4. zones -------------------------------------------------------------------


def test_correct_zones_are_present(client: TestClient) -> None:
    body = _post(client, GOLDEN_REQUEST).json()
    assert {z["zone_id"] for z in body["zones"]} == ZONES_EXPECTED
    assert {m["zone_id"] for m in body["measurements"]} == ZONES_EXPECTED


# --- 5. timestamps --------------------------------------------------------------


def test_timestamps_are_valid_ordered_and_15_min_apart(client: TestClient) -> None:
    body = _post(client, NORMAL_REQUEST).json()
    measurements = body["measurements"]
    assert body["run"]["measurement_count"] == len(measurements)

    timestamps = [_parse(m["timestamp"]) for m in measurements]
    assert all(t.tzinfo is not None for t in timestamps)

    for zone_id in ZONES_EXPECTED:
        zone_ts = sorted({_parse(m["timestamp"]) for m in _zone_measurements(measurements, zone_id)})
        assert len(zone_ts) == _MEASUREMENTS_PER_ZONE_DAY
        assert zone_ts[0] == datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert zone_ts[-1] == datetime(2026, 1, 1, 23, 45, tzinfo=timezone.utc)
        for previous, current in zip(zone_ts, zone_ts[1:]):
            assert current - previous == timedelta(minutes=15)


def test_measurements_are_timestamp_major_ordered(client: TestClient) -> None:
    body = _post(client, NORMAL_REQUEST).json()
    timestamps = [_parse(m["timestamp"]) for m in body["measurements"]]
    assert timestamps == sorted(timestamps)


# --- 6/7. authoritative values and units ----------------------------------------


def test_measurements_contain_only_authoritative_simulator_values(client: TestClient) -> None:
    body = _post(client, GOLDEN_REQUEST).json()
    for m in body["measurements"]:
        assert set(m) == {"timestamp", "zone_id", "metric", "value", "unit"}
        assert m["zone_id"] in ZONES_EXPECTED
        assert m["metric"] in METRICS
        assert math.isfinite(m["value"])
        assert m["unit"] == UNITS[m["metric"]]


def test_units_match_the_simulator_model(client: TestClient) -> None:
    body = _post(client, NORMAL_REQUEST).json()
    by_metric: dict[str, set[str]] = {metric: set() for metric in METRICS}
    for m in body["measurements"]:
        by_metric[m["metric"]].add(m["unit"])
    assert {metric: units for metric, units in by_metric.items()} == {
        metric: {unit} for metric, unit in UNITS.items()
    }


def test_measurements_match_simulator_result_exactly(client: TestClient) -> None:
    body = _post(client, GOLDEN_REQUEST).json()
    result: SimulationResult = run_simulation(
        build_config(seed=42, duration_hours=24.0, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",))
    )
    expected = [_as_measurement_tuple(m) for m in body["measurements"]]
    actual = [
        (m.timestamp.isoformat().replace("+00:00", "Z"), m.zone_id, m.metric, m.value, m.unit)
        for m in sorted(result.measurements, key=lambda x: (x.timestamp, x.zone_id, x.metric))
    ]
    assert expected == actual


def _as_measurement_tuple(m: dict) -> tuple:
    return (m["timestamp"], m["zone_id"], m["metric"], m["value"], m["unit"])


# --- 8/9. determinism ------------------------------------------------------------


def test_same_seed_and_scenario_produce_identical_telemetry(client: TestClient) -> None:
    first = _post(client, GOLDEN_REQUEST).json()
    second = _post(client, GOLDEN_REQUEST).json()
    assert first["run"]["run_id"] == second["run"]["run_id"]
    assert first["measurements"] == second["measurements"]
    assert first["zones"] == second["zones"]
    assert first["scenarios"] == second["scenarios"]


def test_different_seed_changes_stochastic_measurements(client: TestClient) -> None:
    seed_42 = _post(client, {"seed": 42, "days": 1}).json()
    seed_43 = _post(client, {"seed": 43, "days": 1}).json()
    values_42 = [m["value"] for m in seed_42["measurements"]]
    values_43 = [m["value"] for m in seed_43["measurements"]]
    assert values_42 != values_43


# --- 10/11. scenario isolation ---------------------------------------------------


def test_zone_b_incident_affects_only_zone_b(client: TestClient) -> None:
    normal = _post(client, NORMAL_REQUEST).json()["measurements"]
    golden = _post(client, GOLDEN_REQUEST).json()["measurements"]
    normal_by_key = _by_key(normal)
    golden_by_key = _by_key(golden)

    assert set(golden_by_key) == set(normal_by_key)
    for zone_id in ("A", "C", "D"):
        zone_keys = {k for k in golden_by_key if k[1] == zone_id}
        assert all(golden_by_key[k] == normal_by_key[k] for k in zone_keys), zone_id

    zone_b_keys = {k for k in golden_by_key if k[1] == "B"}
    assert any(golden_by_key[k] != normal_by_key[k] for k in zone_b_keys)


def test_zones_acd_are_identical_to_the_corresponding_normal_run(client: TestClient) -> None:
    normal = _post(client, NORMAL_REQUEST).json()["measurements"]
    golden = _post(client, GOLDEN_REQUEST).json()["measurements"]
    normal_by_key = _by_key(normal)
    golden_by_key = _by_key(golden)
    for zone_id in ("A", "C", "D"):
        assert {
            k: v for k, v in golden_by_key.items() if k[1] == zone_id
        } == {
            k: v for k, v in normal_by_key.items() if k[1] == zone_id
        }


def test_zone_b_only_in_window_values_change(client: TestClient) -> None:
    normal = _by_key(_post(client, NORMAL_REQUEST).json()["measurements"])
    golden = _by_key(_post(client, GOLDEN_REQUEST).json()["measurements"])
    window_start = "2026-01-01T06:00:00Z"
    window_end = "2026-01-01T12:00:00Z"
    for key, value in golden.items():
        if key[1] != "B":
            continue
        in_window = window_start <= key[0] < window_end
        if in_window:
            assert value != normal[key]
        else:
            assert value == normal[key]


def test_golden_window_behavior_matches_simulator_semantics(client: TestClient) -> None:
    body = _post(client, GOLDEN_REQUEST).json()
    deltas = _window_means(body["measurements"], "B")
    assert deltas["pressure"] < 0.0  # pressure drops to ~50%
    assert deltas["flow"] > 0.0  # inflow rises (lost water)
    assert deltas["consumption"] < 0.0  # usable demand falls
    assert deltas["quality"] < 0.0  # slight quality degradation


# --- 12/13/14. validation --------------------------------------------------------


def test_unknown_scenario_returns_422(client: TestClient) -> None:
    assert "ZONE_B_SUPPLY_INCIDENT" in SCENARIOS
    response = _post(client, {"seed": 42, "days": 1, "scenario": "NOT_REGISTERED"})
    assert response.status_code == 422
    assert "detail" in response.json()
    assert "ZONE_B_SUPPLY_INCIDENT" in response.json()["detail"]


@pytest.mark.parametrize(
    "payload",
    [
        {"seed": -1},
        {"seed": 100_001},
        {"days": 0},
        {"days": 99},
        {"days": -2},
        {"scenario": "NOT_A_REGISTERED_SCENARIO"},
        {"scenario": 123},
        {"seed": "not-an-int"},
        {"days": "x"},
    ],
)
def test_invalid_seed_or_days_returns_422(client: TestClient, payload) -> None:
    response = _post(client, payload)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_malformed_body_returns_422(client: TestClient) -> None:
    response = client.post("/api/v1/telemetry/run", content=b"{not json", headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_missing_body_returns_422(client: TestClient) -> None:
    assert _post(client).status_code == 422


def test_empty_json_uses_defaults(client: TestClient) -> None:
    body = _post(client, {}).json()
    assert body["run"]["seed"] == 42
    assert body["run"]["days"] == 1.0
    assert body["run"]["scenario"] is None


# --- 15. no AI -------------------------------------------------------------------


def test_telemetry_contains_no_ai_fields_or_markers(client: TestClient) -> None:
    body = _post(client, GOLDEN_REQUEST).json()
    assert "ai" not in body
    assert "analysis" not in body
    rendered = json.dumps(body)
    for marker in ("GEMINI_API_KEY", "Provider", "orchestrator", "Traceback", "fallback"):
        assert marker not in rendered


# --- 16. no database -------------------------------------------------------------


def test_telemetry_has_no_database_dependency(client: TestClient) -> None:
    body = _post(client, NORMAL_REQUEST).json()
    rendered = json.dumps(body)
    for marker in ("database", "db_url", "sqlalchemy", "psycopg"):
        assert marker not in rendered


# --- 17. no FastAPI coupling inside simulation -----------------------------------


def test_simulation_package_has_no_fastapi_or_pydantic_imports() -> None:
    import ast
    import pathlib

    from app import simulation as simulation_package

    sim_dir = pathlib.Path(simulation_package.__file__).parent
    banned = ("fastapi", "pydantic")
    for pyfile in sorted(sim_dir.glob("*.py")):
        tree = ast.parse(pyfile.read_text(encoding="utf-8"), filename=str(pyfile))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.lower().split(".")[0] in banned, pyfile
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").lower().split(".")[0] in banned, pyfile


# --- 19. /analysis/run behavior unchanged ----------------------------------------


def test_analysis_run_unchanged_after_telemetry_addition(client: TestClient) -> None:
    response = client.post("/api/v1/analysis/run", json=NORMAL_REQUEST)
    assert response.status_code == 200
    body = response.json()
    assert body["incidents"] == []
    assert set(body) == {"run", "incidents", "summary"}
    assert body["summary"]["zones"] == 4
    assert body["run"]["data_source"] == "deterministic-simulation"