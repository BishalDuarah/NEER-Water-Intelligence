"""Phase 3-C1 tests: FastAPI analysis endpoint.

Covers the API boundary: request validation, normal run (zero incidents), golden
Zone B deterministic values, AI success vs fallback semantics, no secret/stack
trace leakage, response compactness, health endpoints still working, and the
guarantee that API tests never touch Gemini (orchestrator is overridden with
stub providers) nor require database persistence.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.api.routes.analysis import get_orchestrator
from app.intelligence import (
    AIIncidentAnalysis,
    AIOrchestrator,
    InvestigationAction,
    PossibleCause,
    ProviderUnavailableError,
    ResponseOption,
    Uncertainty,
)
from app.main import app
from app.simulation import SCENARIOS

GOLDEN_REQUEST = {
    "seed": 42,
    "days": 1,
    "scenario": "ZONE_B_SUPPLY_INCIDENT",
}
NORMAL_REQUEST = {"seed": 42, "days": 1}


def _valid_analysis(incident_id: str) -> AIIncidentAnalysis:
    return AIIncidentAnalysis(
        incident_id=incident_id,
        summary="AI summary: signals are consistent with a potential water-loss event.",
        evidence_interpretation="Pressured decline and flow increase are consistent.",
        possible_causes=[
            PossibleCause(
                cause="Consistent with a potential water loss event.",
                framing="consistent",
                supporting_evidence=["pressure below baseline", "flow above baseline"],
            )
        ],
        investigation_actions=[
            InvestigationAction(
                action="Verify the zone's readings against the baseline.",
                category="evidence-verification",
                priority=1,
                rationale="Ground next steps on deterministic evidence.",
            )
        ],
        response_options=[
            ResponseOption(
                recommendation="An operator may verify the incident evidence.",
                priority=1,
                rationale="Assign the decision to a human operator.",
            )
        ],
        uncertainty=Uncertainty(supported=["Evidence score is 0.985."]),
        safety_notes=["Decision support only."],
    )


class OkProvider:
    """Fake AI provider that always returns a valid analysis."""

    def generate_analysis(self, context):
        return _valid_analysis(context.incident.incident_id)


class FailProvider:
    """Fake AI provider that always raises a provider error."""

    def generate_analysis(self, context):
        raise ProviderUnavailableError("GEMINI_API_KEY missing (test override)")


@pytest.fixture
def ok_orchestrator() -> AIOrchestrator:
    return AIOrchestrator(OkProvider())


@pytest.fixture
def fail_orchestrator() -> AIOrchestrator:
    return AIOrchestrator(FailProvider())


@pytest.fixture
def override_orchestrator(client: TestClient):
    @contextmanager
    def _apply(orchestrator: AIOrchestrator) -> Iterator[None]:
        app.dependency_overrides[get_orchestrator] = lambda: orchestrator
        try:
            yield
        finally:
            app.dependency_overrides.pop(get_orchestrator, None)

    return _apply


@pytest.fixture
def golden_with_fallback(client: TestClient, override_orchestrator):
    with override_orchestrator(AIOrchestrator(FailProvider())):
        response = client.post("/api/v1/analysis/run", json=GOLDEN_REQUEST)
        assert response.status_code == 200
        yield response


# --- existing health endpoints -------------------------------------------------


def test_root_health_still_works(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_v1_health_still_works(client: TestClient) -> None:
    body = client.get("/api/v1/health").json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body


# --- request validation --------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"seed": -1},
        {"days": 0},
        {"days": 99},
        {"scenario": "NOT_A_REGISTERED_SCENARIO"},
        {"scenario": 123},
        {"seed": "not-an-int"},
    ],
)
def test_invalid_request_returns_validation_error(client: TestClient, payload) -> None:
    response = client.post("/api/v1/analysis/run", json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()


def test_request_rejects_unknown_scenario_via_registry(client: TestClient) -> None:
    assert "ZONE_B_SUPPLY_INCIDENT" in SCENARIOS
    response = client.post(
        "/api/v1/analysis/run",
        json={"seed": 42, "days": 1, "scenario": "ZONE_B_SUPPLY_INCIDENT"},
    )
    assert response.status_code == 200


def test_analysis_uses_registered_scenario_registry() -> None:
    assert set(SCENARIOS) == {"ZONE_B_SUPPLY_INCIDENT"}


# --- normal run ----------------------------------------------------------------


def test_normal_run_returns_200(client: TestClient) -> None:
    response = client.post("/api/v1/analysis/run", json=NORMAL_REQUEST)
    assert response.status_code == 200


def test_normal_run_returns_zero_incidents(client: TestClient) -> None:
    body = client.post("/api/v1/analysis/run", json=NORMAL_REQUEST).json()
    assert body["incidents"] == []
    assert body["summary"]["incidents"] == 0
    assert body["summary"]["ai_source_count"] == 0
    assert body["summary"]["fallback_count"] == 0
    assert body["summary"]["zones"] == 4


def test_normal_run_metadata_marks_deterministic_simulation(client: TestClient) -> None:
    body = client.post("/api/v1/analysis/run", json=NORMAL_REQUEST).json()
    run = body["run"]
    assert run["data_source"] == "deterministic-simulation"
    assert run["seed"] == 42
    assert run["days"] == 1
    assert run["scenario"] is None


# --- golden Zone B (deterministic values, AI fallback path) --------------------


def test_golden_run_returns_one_incident(golden_with_fallback) -> None:
    body = golden_with_fallback.json()
    assert body["summary"]["incidents"] == 1
    assert len(body["incidents"]) == 1


def test_golden_deterministic_incident_values(golden_with_fallback) -> None:
    incident = golden_with_fallback.json()["incidents"][0]["incident"]
    assert incident["zone_id"] == "B"
    assert incident["incident_type"] == "WATER_LOSS"
    assert incident["severity"] == "CRITICAL"
    assert incident["risk_score"] == pytest.approx(91.52, abs=0.01)
    assert incident["confidence"] == pytest.approx(0.9918, abs=0.0005)
    assert incident["estimated_affected_population"] == 32000
    assert incident["incident_id"].startswith("INC-B-")


def test_golden_evidence_values(golden_with_fallback) -> None:
    evidence = golden_with_fallback.json()["incidents"][0]["evidence"]
    assert evidence["evidence_score"] == pytest.approx(0.985, abs=0.001)
    assert set(evidence["signal_types"]) == {"flow", "pressure", "quality", "consumption"}
    assert evidence["sensor_anomaly_count"] == 89
    assert evidence["citizen_report_count"] == 12
    assert evidence["persistence_minutes"] == 345
    assert {s["metric"] for s in evidence["contributing_signals"]} == {
        "flow",
        "pressure",
        "quality",
        "consumption",
    }


def test_golden_ai_fallback_semantics(golden_with_fallback) -> None:
    incident = golden_with_fallback.json()["incidents"][0]
    assert incident["ai"]["source"] == "FALLBACK"
    assert incident["ai"]["ai_available"] is False
    assert incident["ai"]["fallback_reason"] == "PROVIDER_UNAVAILABLE"
    assert "summary" in incident["analysis"]
    body = golden_with_fallback.json()
    assert body["summary"]["fallback_count"] == 1
    assert body["summary"]["ai_source_count"] == 0


# --- AI success path -----------------------------------------------------------


def test_ai_success_path_returns_source_ai(client: TestClient, override_orchestrator) -> None:
    with override_orchestrator(AIOrchestrator(OkProvider())):
        body = client.post("/api/v1/analysis/run", json=GOLDEN_REQUEST).json()
    incident = body["incidents"][0]
    assert incident["ai"]["source"] == "AI"
    assert incident["ai"]["ai_available"] is True
    assert incident["ai"]["fallback_reason"] is None
    assert body["summary"]["ai_source_count"] == 1
    assert body["summary"]["fallback_count"] == 0


# --- AI failure never alters the deterministic record --------------------------


def test_ai_failure_keeps_deterministic_record_identical_to_ai_success(
    client: TestClient, override_orchestrator
) -> None:
    def run_with(orchestrator: AIOrchestrator) -> dict:
        with override_orchestrator(orchestrator):
            body = client.post("/api/v1/analysis/run", json=GOLDEN_REQUEST).json()
        return body["incidents"][0]["incident"]

    ok_incident = run_with(AIOrchestrator(OkProvider()))
    fail_incident = run_with(AIOrchestrator(FailProvider()))
    assert ok_incident == fail_incident
    assert fail_incident["severity"] == "CRITICAL"
    assert fail_incident["risk_score"] == pytest.approx(91.52, abs=0.01)


# --- secrets / stack traces / compactness --------------------------------------


@pytest.mark.parametrize(
    "banned",
    [
        "GEMINI_API_KEY",
        "Traceback",
        "traceback",
        "ProviderUnavailableError",
        "dependencies",
        ".venv",
        "psycopg",
        "secret",
    ],
)
def test_response_contains_no_secret_or_stack_trace(
    golden_with_fallback, banned: str
) -> None:
    body = golden_with_fallback.json()
    assert banned not in json.dumps(body)


def test_response_is_compact_without_raw_measurements(golden_with_fallback) -> None:
    body = golden_with_fallback.json()
    assert "measurements" not in json.dumps(body)
    assert "measurement" not in json.dumps(body)
    incident = body["incidents"][0]
    assert set(incident) == {"incident", "evidence", "ai", "analysis"}


def test_response_has_no_http_500_for_provider_failure(golden_with_fallback) -> None:
    assert golden_with_fallback.status_code == 200