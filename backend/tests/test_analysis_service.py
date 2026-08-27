"""Phase 3-C1 tests: analysis application service.

Covers the service layer directly (no HTTP): orchestrator injection, expected
scenario errors, zero-incident normal runs, golden Zone B determinism and
non-mutation (the response matches a freshly recomputed pipeline result, and
running twice yields identical deterministic fields), single AI invocation per
qualified incident, and AI failure never altering the deterministic record.
"""

from __future__ import annotations

import pytest

from app.intelligence import (
    AIIncidentAnalysis,
    AIOrchestrator,
    AnalysisResult,
    AnalysisSource,
    FallbackReason,
    InvestigationAction,
    PossibleCause,
    ProviderUnavailableError,
    ResponseOption,
    Uncertainty,
    assess_groups,
    build_ai_context,
    correlate_evidence,
    detect_anomalies,
)
from app.schemas.analysis import AnalysisRunRequest
from app.services.analysis import (
    AnalysisService,
    UnknownScenarioError,
)
from app.simulation import SCENARIOS, build_config, run_simulation

REFERENCE_SEED = 99
REFERENCE_DAYS = 7.0


def _valid_analysis(incident_id: str) -> AIIncidentAnalysis:
    return AIIncidentAnalysis(
        incident_id=incident_id,
        summary="Service-level AI summary.",
        evidence_interpretation="Signals are consistent with a potential water-loss event.",
        possible_causes=[
            PossibleCause(
                cause="Consistent with a potential water loss event.",
                framing="consistent",
            )
        ],
        investigation_actions=[
            InvestigationAction(
                action="Verify the zone readings.",
                category="evidence-verification",
                priority=1,
                rationale="Ground next steps on deterministic evidence.",
            )
        ],
        response_options=[
            ResponseOption(
                recommendation="An operator may verify the evidence.",
                priority=1,
                rationale="Assign the decision to an operator.",
            )
        ],
        uncertainty=Uncertainty(supported=["Evidence score is 0.985."]),
        safety_notes=["Decision support only."],
    )


class RecordingProvider:
    """Fake provider that records every context it receives."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list = []
        self.contexts: list = []

    def generate_analysis(self, context):
        self.calls.append(context)
        self.contexts.append(context.model_dump())
        if self.error is not None:
            raise self.error
        return _valid_analysis(context.incident.incident_id)


def _golden_request(**overrides) -> AnalysisRunRequest:
    params = {"seed": 42, "days": 1.0, "scenario": "ZONE_B_SUPPLY_INCIDENT"}
    params.update(overrides)
    return AnalysisRunRequest(**params)


def _recompute_golden_incident_fields():
    """Fresh deterministic recomputation (independent of the service)."""
    target = run_simulation(
        build_config(
            seed=42,
            duration_hours=24.0,
            scenario_ids=("ZONE_B_SUPPLY_INCIDENT",),
        )
    )
    reference = run_simulation(
        build_config(seed=REFERENCE_SEED, duration_hours=REFERENCE_DAYS * 24.0)
    )
    correlation = correlate_evidence(
        detect_anomalies(reference.measurements, target.measurements),
        target.reports,
    )
    qualified = [
        a
        for a in assess_groups(correlation.groups, target.zones)
        if a.qualified and a.incident is not None
    ]
    assert len(qualified) == 1
    incident = qualified[0].incident
    assert incident is not None
    return {
        "incident_id": incident.incident_id,
        "zone_id": incident.zone_id,
        "incident_type": incident.incident_type.value,
        "severity": incident.severity.value,
        "risk_score": incident.risk_score,
        "confidence": incident.confidence,
        "estimated_affected_population": incident.estimated_affected_population,
    }


def test_service_accepts_injected_orchestrator() -> None:
    provider = RecordingProvider()
    service = AnalysisService(AIOrchestrator(provider))
    assert service is not None


def test_service_builds_default_orchestrator_when_none() -> None:
    service = AnalysisService()
    assert isinstance(service._orchestrator, AIOrchestrator)


def test_service_rejects_unknown_scenario() -> None:
    service = AnalysisService()
    with pytest.raises(UnknownScenarioError):
        service.run_analysis(AnalysisRunRequest(scenario="NOT_REGISTERED"))


def test_service_uses_scenario_registry() -> None:
    assert SCENARIOS["ZONE_B_SUPPLY_INCIDENT"].id == "ZONE_B_SUPPLY_INCIDENT"


def test_normal_run_returns_zero_incidents() -> None:
    service = AnalysisService(AIOrchestrator(RecordingProvider()))
    response = service.run_analysis(AnalysisRunRequest(seed=42, days=1.0))
    assert response.incidents == []
    assert response.summary.incidents == 0


def test_golden_run_invokes_orchestrator_exactly_once() -> None:
    provider = RecordingProvider()
    service = AnalysisService(AIOrchestrator(provider))
    response = service.run_analysis(_golden_request())
    assert response.summary.incidents == 1
    assert len(provider.calls) == 1
    assert provider.contexts[0]["incident"]["zone_id"] == "B"


def test_golden_deterministic_values_match_fresh_recompute() -> None:
    provider = RecordingProvider()
    service = AnalysisService(AIOrchestrator(provider))
    response = service.run_analysis(_golden_request())
    incident = response.incidents[0].incident
    expected = _recompute_golden_incident_fields()
    assert incident.incident_id == expected["incident_id"]
    assert incident.zone_id == expected["zone_id"]
    assert incident.incident_type.value == expected["incident_type"]
    assert incident.severity.value == expected["severity"]
    assert incident.risk_score == expected["risk_score"]
    assert incident.confidence == expected["confidence"]
    assert incident.estimated_affected_population == expected["estimated_affected_population"]
    assert incident.risk_score == pytest.approx(91.52, abs=0.01)
    assert incident.confidence == pytest.approx(0.9918, abs=0.0005)


def test_service_is_deterministic_across_runs() -> None:
    service = AnalysisService(AIOrchestrator(RecordingProvider()))
    first = service.run_analysis(_golden_request())
    second = service.run_analysis(_golden_request())
    assert first.incidents == second.incidents
    assert first.summary == second.summary


def test_service_does_not_mutate_orchestrator_inputs() -> None:
    provider = RecordingProvider()
    service = AnalysisService(AIOrchestrator(provider))
    service.run_analysis(_golden_request())
    context_before = provider.contexts[0]
    service.run_analysis(_golden_request())
    assert provider.contexts[0] == context_before


def test_ai_failure_path_preserves_deterministic_incident() -> None:
    provider = RecordingProvider(error=ProviderUnavailableError("no key"))
    service = AnalysisService(AIOrchestrator(provider))
    response = service.run_analysis(_golden_request())
    incident_out = response.incidents[0]
    assert incident_out.incident.incident_type.value == "WATER_LOSS"
    assert incident_out.incident.severity.value == "CRITICAL"
    assert incident_out.incident.risk_score == pytest.approx(91.52, abs=0.01)
    assert incident_out.ai.source is AnalysisSource.FALLBACK
    assert incident_out.ai.ai_available is False
    assert incident_out.ai.fallback_reason is FallbackReason.PROVIDER_UNAVAILABLE
    assert response.summary.fallback_count == 1


def test_ai_success_path_marks_source_ai() -> None:
    service = AnalysisService(AIOrchestrator(RecordingProvider()))
    response = service.run_analysis(_golden_request())
    assert response.incidents[0].ai.source is AnalysisSource.AI
    assert response.incidents[0].ai.ai_available is True
    assert response.incidents[0].ai.fallback_reason is None
    assert response.summary.ai_source_count == 1


def test_run_metadata_reflects_request() -> None:
    service = AnalysisService(AIOrchestrator(RecordingProvider()))
    response = service.run_analysis(_golden_request())
    metadata = response.run
    assert metadata.run_id == "run-42-1-99-ZONE_B_SUPPLY_INCIDENT"
    assert metadata.seed == 42
    assert metadata.days == 1.0
    assert metadata.scenario == "ZONE_B_SUPPLY_INCIDENT"
    assert metadata.reference_seed == 99
    assert metadata.data_source == "deterministic-simulation"


def test_analysis_result_contract_reused() -> None:
    assert AnalysisResult
    assert AnalysisSource.AI == "AI"
    assert AnalysisSource.FALLBACK == "FALLBACK"