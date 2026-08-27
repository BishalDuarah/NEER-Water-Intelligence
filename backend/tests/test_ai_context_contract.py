"""Phase 3-B1 tests: AI context models + provider interface.

Covers context construction/projection from real Phase 2C incidents, risk and
evidence mapping, missing-optional handling, minimization (no unrelated zones,
no secrets, no raw reprs), deterministic JSON serialization, the AI output
schema validation (required fields, ranges, incident_id reference, causal
framing, advisory responses, uncertainty), the provider interface (fake
provider + zero network), authoritative-field protection, determinism of
identical input, golden Zone B values, and the architectural guard that no LLM
SDK/network dependency exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.intelligence import (
    AIIncidentAnalysis,
    AIProvider,
    AIProviderError,
    AIValidationError,
    Incident,
    IncidentAIContext,
    IncidentStatus,
    IncidentType,
    InvestigationAction,
    MalformedAIResponseError,
    PossibleCause,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ResponseOption,
    SeverityLabel,
    Uncertainty,
    assess_group,
    assess_groups,
    build_ai_context,
    correlate_evidence,
    detect_anomalies,
    serialize_context,
)
from app.simulation import build_config, run_simulation
from app.simulation.models import Measurement

REFERENCE_SEED = 99
REFERENCE_DAYS = 7.0
GOLDEN_SEED = 42

FORBIDDEN_SDK_TOKENS = (
    "google", "gemini", "openai", "anthropic", "import requests",
    "import httpx", "import urllib", "socket", "aiohttp", "http.client",
    "google.generativeai", "google.genai",
)


@pytest.fixture(scope="module")
def reference_measurements() -> list[Measurement]:
    return run_simulation(
        build_config(seed=REFERENCE_SEED, duration_hours=REFERENCE_DAYS * 24.0)
    ).measurements


@pytest.fixture(scope="module")
def golden_incident(reference_measurements) -> Incident:
    incident_run = run_simulation(
        build_config(seed=GOLDEN_SEED, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",))
    )
    correlation = correlate_evidence(
        detect_anomalies(reference_measurements, incident_run.measurements), incident_run.reports
    )
    assessments = assess_groups(correlation.groups, incident_run.zones)
    qualified = [a for a in assessments if a.qualified]
    assert len(qualified) == 1
    incident = qualified[0].incident
    assert incident is not None
    return incident


@pytest.fixture(scope="module")
def golden_context(golden_incident) -> IncidentAIContext:
    return build_ai_context(golden_incident)


# --- 1..5. context construction & projection ---------------------------------

def test_incident_ai_context_creation(golden_context) -> None:
    assert isinstance(golden_context, IncidentAIContext)
    for section in ("incident", "evidence", "risk", "classification"):
        assert hasattr(golden_context, section)


def test_context_built_from_real_phase2c_incident(
    golden_incident, golden_context
) -> None:
    expected = golden_incident.incident_id
    assert golden_context.incident.incident_id == expected
    assert golden_context.incident.zone_id == golden_incident.zone_id
    assert golden_context.incident.incident_type == golden_incident.incident_type
    assert golden_context.incident.risk_score == golden_incident.risk_score
    assert golden_context.incident.confidence == golden_incident.confidence
    assert golden_context.incident.start_time == golden_incident.start_time
    assert golden_context.incident.last_updated == golden_incident.last_updated
    assert (
        golden_context.incident.estimated_affected_population
        == golden_incident.estimated_affected_population
    )


def test_risk_factors_map(golden_incident, golden_context) -> None:
    factors = golden_incident.risk_factors
    risk = golden_context.risk
    assert risk.evidence_strength == factors.evidence_strength
    assert risk.anomaly_severity == factors.anomaly_severity
    assert risk.persistence == factors.persistence
    assert risk.impact == factors.impact
    assert risk.citizen_context == factors.citizen_context
    assert risk.risk_score == golden_incident.risk_score


def test_correlation_evidence_maps(golden_incident, golden_context) -> None:
    group = golden_incident.evidence
    evidence = golden_context.evidence
    assert evidence.evidence_score == group.evidence_score
    assert evidence.temporal_coherence == group.temporal_coherence
    assert evidence.spatial_coherence == group.spatial_coherence
    assert evidence.signal_diversity == group.signal_diversity
    assert evidence.persistence_minutes == group.persistence_minutes
    assert evidence.sensor_anomaly_count == group.sensor_anomaly_count
    assert evidence.citizen_report_count == group.citizen_report_count
    assert list(evidence.signal_types) == list(group.signal_types)

    listed = {s.metric: s for s in evidence.contributing_signals}
    assert {s.metric for s in golden_incident.contributing_signals} == set(listed)
    for signal in golden_incident.contributing_signals:
        summary = listed[signal.metric]
        assert summary.direction == signal.direction
        assert summary.anomaly_count == signal.anomaly_count
        assert summary.mean_z == signal.mean_z
        assert summary.mean_abs_z == signal.mean_abs_z


def test_incident_metadata_maps(golden_incident, golden_context) -> None:
    assert golden_context.incident.incident_id == golden_incident.incident_id
    assert golden_context.incident.status == IncidentStatus.DETECTED
    assert golden_context.incident.severity == golden_incident.severity
    assert golden_context.classification.incident_type == golden_incident.incident_type
    assert (
        golden_context.classification.classification_reason
        == golden_incident.classification_reason
    )
    assert golden_context.classification.classification_support > 0.9


# --- 6. missing optional information ------------------------------------------

def test_missing_optional_information_handled(reference_measurements) -> None:
    incident_run = run_simulation(
        build_config(seed=GOLDEN_SEED, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",))
    )
    correlation = correlate_evidence(
        detect_anomalies(reference_measurements, incident_run.measurements), None
    )
    top = max(correlation.groups, key=lambda g: g.evidence_score)
    assessment = assess_group(top, zones=None)  # no zones => no population
    assert assessment.qualified
    incident = assessment.incident
    assert incident is not None
    assert incident.estimated_affected_population is None
    assert incident.evidence.citizen_report_count == 0

    context = build_ai_context(incident)
    assert context.incident.estimated_affected_population is None
    assert context.evidence.citizen_report_count == 0
    assert context.evidence.citizen_report_summaries == []


# --- 7..11. minimization & serialization --------------------------------------

def test_context_contains_no_unrelated_zones(golden_context) -> None:
    payload = serialize_context(golden_context)
    assert golden_context.incident.zone_id == "B"
    assert golden_context.evidence is not None
    for other in ("Zone A", "Zone C", "Zone D", "Riverside is not included"):
        assert other not in payload


def test_context_contains_no_secrets(golden_context) -> None:
    payload = serialize_context(golden_context).lower()
    for secret_token in (
        "password", "passwd", "api_key", "apikey", "secret",
        "credential", "token", "database_url", ".env", "private_key",
    ):
        assert secret_token not in payload


def test_serialization_is_deterministic(golden_incident) -> None:
    first = build_ai_context(golden_incident)
    second = build_ai_context(golden_incident)
    assert serialize_context(first) == serialize_context(second)
    assert serialize_context(first) == serialize_context(first)


def test_serialization_is_json_compatible(golden_context) -> None:
    payload = serialize_context(golden_context)
    parsed = json.loads(payload)
    assert parsed["incident"]["incident_id"].startswith("INC-B-")
    assert isinstance(parsed["incident"]["risk_score"], float)
    assert isinstance(parsed["incident"]["start_time"], str)
    assert isinstance(parsed["evidence"]["sensor_anomaly_count"], int)
    assert isinstance(parsed["classification"]["incident_type"], str)

    def json_native(obj) -> None:
        if isinstance(obj, dict):
            for value in obj.values():
                json_native(value)
        elif isinstance(obj, list):
            for item in obj:
                json_native(item)
        else:
            assert isinstance(obj, (str, int, float, bool)) or obj is None

    json_native(parsed)


def test_no_raw_object_reprs(golden_context) -> None:
    payload = serialize_context(golden_context)
    assert "Incident(" not in payload
    assert "CorrelatedEvidenceGroup(" not in payload
    assert "AnomalyResult(" not in payload
    assert "CitizenReport(" not in payload
    assert "at 0x" not in payload
    assert "datetime(" not in payload and "<" not in payload


# --- 12..19. AI output schema validation --------------------------------------

def _valid_analysis(incident_id: str = "INC-B-20260101T060000Z") -> AIIncidentAnalysis:
    return AIIncidentAnalysis(
        incident_id=incident_id,
        summary="Zone B shows signals consistent with a potential water-loss event.",
        evidence_interpretation="Pressure decline with increased inflow and reduced consumption.",
        possible_causes=[
            PossibleCause(
                cause="possible pipeline leak",
                framing="consistent",
                supporting_evidence=["pressure below expected", "inflow above expected"],
            )
        ],
        investigation_actions=[
            InvestigationAction(
                action="inspect zone B pressure-control valves",
                category="inspect_pressure_infrastructure",
                priority=1,
                rationale="grounded in pressure anomaly and flow increase",
            )
        ],
        response_options=[
            ResponseOption(
                recommendation="increase monitoring of zone B",
                priority=1,
                rationale="sustained multi-signal deviation",
            )
        ],
        uncertainty=Uncertainty(
            supported=["multi-signal deviation pattern"],
            uncertain=["physical cause attribution"],
            additional_information=["neighboring-zone flow comparison"],
        ),
        safety_notes=["No autonomous action is recommended."],
    )


def test_valid_ai_analysis_passes_validation() -> None:
    analysis = _valid_analysis()
    assert isinstance(analysis, AIIncidentAnalysis)
    assert analysis.incident_id.startswith("INC-B-")
    assert analysis.summary
    assert analysis.evidence_interpretation


def test_missing_required_output_fields_fail() -> None:
    base = _valid_analysis()
    for field in ("incident_id", "summary", "evidence_interpretation"):
        data = base.model_dump()
        del data[field]
        with pytest.raises(ValidationError):
            AIIncidentAnalysis(**data)


def test_invalid_score_range_values_fail() -> None:
    base = _valid_analysis()
    with pytest.raises(ValidationError):
        AIIncidentAnalysis(
            **{
                **base.model_dump(),
                "investigation_actions": [
                    InvestigationAction(action="x", category=None, priority=0, rationale="y")
                ],
            }
        )
    with pytest.raises(ValidationError):
        AIIncidentAnalysis(
            **{
                **base.model_dump(),
                "response_options": [
                    ResponseOption(recommendation="x", priority=-1, rationale="y")
                ],
            }
        )


def test_invalid_incident_id_reference_fails() -> None:
    for bad_id in ("", "water-loss-1", "INC-B-20260101", "INCB-20260101T060000Z"):
        with pytest.raises(ValidationError):
            _valid_analysis(incident_id=bad_id)


def test_possible_causes_preserve_supporting_evidence() -> None:
    analysis = _valid_analysis()
    cause = analysis.possible_causes[0]
    assert cause.cause == "possible pipeline leak"
    assert cause.framing == "consistent"
    assert cause.supporting_evidence == ["pressure below expected", "inflow above expected"]
    assert cause.notes is None
    with pytest.raises(ValidationError):
        PossibleCause(cause="x", framing="confirmed")


def test_investigation_actions_preserve_priority_and_rationale() -> None:
    analysis = _valid_analysis()
    action = analysis.investigation_actions[0]
    assert action.action == "inspect zone B pressure-control valves"
    assert action.category == "inspect_pressure_infrastructure"
    assert action.priority == 1
    assert action.rationale.startswith("grounded in")


def test_response_options_remain_advisory() -> None:
    analysis = _valid_analysis()
    option = analysis.response_options[0]
    assert option.recommendation == "increase monitoring of zone B"
    assert option.advisory is True
    with pytest.raises(ValidationError):
        ResponseOption(recommendation="close the valve", advisory=False)


def test_uncertainty_structure() -> None:
    analysis = _valid_analysis()
    assert analysis.uncertainty.supported == ["multi-signal deviation pattern"]
    assert analysis.uncertainty.uncertain == ["physical cause attribution"]
    assert analysis.uncertainty.additional_information == ["neighboring-zone flow comparison"]
    empty = AIIncidentAnalysis(incident_id="INC-B-20260101T060000Z", summary="s", evidence_interpretation="e")
    assert Uncertainty() == empty.uncertainty


# --- 20..22. provider interface -----------------------------------------------

class FakeAIProvider:
    """Minimal in-test provider: implements AIProvider, performs no I/O."""

    def generate_analysis(self, context: IncidentAIContext) -> AIIncidentAnalysis:
        return AIIncidentAnalysis(
            incident_id=context.incident.incident_id,
            summary="fake but valid summary",
            evidence_interpretation="fake but valid interpretation",
        )


def test_provider_interface_can_be_implemented_by_fake(golden_context) -> None:
    provider = FakeAIProvider()
    assert isinstance(provider, AIProvider)  # runtime_checkable protocol
    analysis = provider.generate_analysis(golden_context)
    assert isinstance(analysis, AIIncidentAnalysis)
    assert analysis.incident_id == golden_context.incident.incident_id


def test_provider_interface_performs_no_network() -> None:
    source_dir = Path(__file__).parent.parent / "app" / "intelligence"
    for module_name in ("ai_context.py", "ai_analysis.py", "ai_provider.py"):
        text = source_dir.joinpath(module_name).read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_SDK_TOKENS:
            assert token not in text, f"{module_name} references forbidden token {token!r}"
    asserts = [m for m in dir(AIProvider) if not m.startswith("_")]
    assert asserts == ["generate_analysis"]


def test_provider_error_types_distinguishable() -> None:
    errors = [
        ProviderUnavailableError("down"),
        ProviderTimeoutError("too slow"),
        MalformedAIResponseError("bad shape"),
        AIValidationError("bad values"),
    ]
    for error in errors:
        assert isinstance(error, AIProviderError)
        assert isinstance(error, Exception)
    assert issubclass(ProviderUnavailableError, AIProviderError)
    assert issubclass(ProviderTimeoutError, AIProviderError)
    assert issubclass(MalformedAIResponseError, AIProviderError)
    assert issubclass(AIValidationError, AIProviderError)


# --- 22. authoritative-field protection ---------------------------------------

def test_ai_output_cannot_redefine_deterministic_fields() -> None:
    fields = set(AIIncidentAnalysis.model_fields)
    forbidden = {"risk_score", "severity", "incident_type", "confidence", "start_time", "population"}
    assert fields.isdisjoint(forbidden)
    assert "risk" not in {f.split("_")[0] for f in fields}


# --- 23. determinism of identical input ---------------------------------------

def test_same_input_produces_identical_context(golden_incident) -> None:
    first = build_ai_context(golden_incident)
    second = build_ai_context(golden_incident, golden_incident.evidence)
    assert first == second
    assert serialize_context(first) == serialize_context(second)


# --- golden Zone B verification -----------------------------------------------

def test_golden_zone_b_context_values(golden_context) -> None:
    incident = golden_context.incident
    assert incident.zone_id == "B"
    assert incident.incident_type == IncidentType.WATER_LOSS
    assert incident.risk_score == pytest.approx(91.52, abs=0.01)
    assert incident.severity == SeverityLabel.CRITICAL
    assert incident.confidence == pytest.approx(0.9918, abs=0.001)
    assert golden_context.evidence.evidence_score == pytest.approx(0.985, abs=0.001)
    assert golden_context.evidence.signal_types == ["consumption", "flow", "pressure", "quality"]
    assert golden_context.evidence.sensor_anomaly_count == 89
    assert golden_context.evidence.citizen_report_count == 12
    assert golden_context.evidence.persistence_minutes == 345
    assert incident.estimated_affected_population == 32_000


# --- deterministic core regression guard --------------------------------------

def test_deterministic_pipeline_regression(reference_measurements, golden_incident) -> None:
    assert golden_incident == golden_incident  # constructible; regression baseline guaranteed by suite
    assert golden_incident.incident_type == IncidentType.WATER_LOSS
    assert golden_incident.evidence.sensor_anomaly_count == 89
    assert golden_incident.evidence.evidence_score == pytest.approx(0.985, abs=0.01)