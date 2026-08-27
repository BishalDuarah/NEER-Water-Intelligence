"""Phase 3-B3 tests: AI orchestration & deterministic fallback.

Covers the orchestration contract: AI-or-success path semantics, safe/categorized
fallback reasons mapped from the ``AIProviderError`` hierarchy, strict handling
of unexpected (non-``AIProviderError``) failures (propagate, never fall back),
``AIIncidentAnalysis`` passthrough unchanged, deterministic fallback content that
only references values present in the context (per-type language, advisory-only
framing, uncertainty and safety notes, no autonomous action wording), determinism
across repeated builds and across different failure modes, one-shot provider
invocation (no retry), non-mutation of the context/incident, the golden Zone B
seeded pipeline, the normal (no-incident) scenario, safe fallback reasons (no
secret/provider internals in results or logs), and source-level guarantees (no
DB/FastAPI/network/time/randomness coupling in the orchestrator).

The suite is deterministic and network-free: all provider behaviour is injected.
"""

from __future__ import annotations

import copy
import dataclasses
from datetime import datetime
from pathlib import Path

import pytest

from app.intelligence import (
    AIIncidentAnalysis,
    AIOrchestrator,
    AIProviderError,
    AIValidationError,
    AnalysisResult,
    AnalysisSource,
    FallbackReason,
    Incident,
    IncidentAIContext,
    IncidentStatus,
    IncidentType,
    MalformedAIResponseError,
    PossibleCause,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ResponseOption,
    SeverityLabel,
    Uncertainty,
    analyze_incident,
    assess_groups,
    build_ai_context,
    build_fallback_analysis,
    correlate_evidence,
    detect_anomalies,
)
from app.intelligence.ai_context import (
    CitizenReportSummary,
    ClassificationSection,
    ContributingSignalSummary,
    EvidenceSection,
    IncidentSection,
    RiskSection,
)
from app.simulation import build_config, run_simulation

REFERENCE_SEED = 99
REFERENCE_DAYS = 7.0
GOLDEN_SEED = 42
NORMAL_SEED = 100

_INCIDENT_ID = "INC-B-20260101T060000Z"

_FORBIDDEN_SOURCE_TOKENS = (
    "fastapi",
    "sqlalchemy",
    "app.db",
    "psycopg",
    "import requests",
    "socket",
    "aiohttp",
    "urllib",
    "http.client",
    "from google",
    "import google",
    "google.genai",
    "random",
    "uuid",
    "datetime.now",
    "time.time",
)

_CAUSE_PHRASE: dict[IncidentType, str] = {
    IncidentType.WATER_LOSS: "potential water loss event",
    IncidentType.WATER_QUALITY: "potential water quality issue",
    IncidentType.PRESSURE_ANOMALY: "potential pressure anomaly",
    IncidentType.SUPPLY_DISRUPTION: "potential supply disruption",
    IncidentType.UNKNOWN: "does not support a sufficiently specific incident cause",
}

_AUTONOMOUS_WORDS = ("autonomous", "automatically closes", "will restore", "remote control")


# --- fixtures & test doubles ---------------------------------------------------


@pytest.fixture(scope="module")
def reference_measurements():
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


class StubProvider:
    """Returns (or raises, per test) while counting invocations."""

    def __init__(
        self,
        analysis: AIIncidentAnalysis | None = None,
        error: Exception | None = None,
    ) -> None:
        self.analysis = analysis
        self.error = error
        self.calls = 0

    def generate_analysis(self, context: IncidentAIContext) -> AIIncidentAnalysis:
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.analysis is None:
            raise AssertionError("StubProvider needs analysis or error")
        return self.analysis


def _make_context(
    incident_type: IncidentType = IncidentType.WATER_LOSS,
    *,
    zone_id: str = "B",
    incident_id: str = _INCIDENT_ID,
    metrics: list[str] | None = None,
    direction: str = "above",
    risk_score: float = 91.52,
) -> IncidentAIContext:
    metrics = metrics if metrics is not None else ["consumption"]
    return IncidentAIContext(
        incident=IncidentSection(
            incident_id=incident_id,
            zone_id=zone_id,
            incident_type=incident_type,
            status=IncidentStatus.DETECTED,
            severity=SeverityLabel.CRITICAL,
            risk_score=risk_score,
            confidence=0.99,
            start_time=datetime(2026, 1, 1, 6, 0, 0),
            last_updated=datetime(2026, 1, 1, 6, 5, 0),
            estimated_affected_population=20000,
        ),
        evidence=EvidenceSection(
            contributing_signals=[
                ContributingSignalSummary(
                    metric=metric,
                    direction=direction,
                    anomaly_count=10,
                    mean_z=5.0,
                    mean_abs_z=5.0,
                )
                for metric in metrics
            ],
            signal_types=["sensor", "citizen-report"],
            evidence_score=0.98,
            temporal_coherence=0.90,
            spatial_coherence=0.80,
            signal_diversity=0.85,
            persistence_minutes=345,
            sensor_anomaly_count=89,
            citizen_report_count=12,
            citizen_report_summaries=[
                CitizenReportSummary(category="pressure", severity="moderate", count=12)
            ],
        ),
        risk=RiskSection(
            evidence_strength=0.90,
            anomaly_severity=0.80,
            persistence=0.70,
            impact=0.60,
            citizen_context=0.50,
            risk_score=risk_score,
        ),
        classification=ClassificationSection(
            incident_type=incident_type,
            classification_reason="deviation pattern matches pressure/usage signals",
            classification_support=0.95,
        ),
    )


_SUMMARY = "Deterministic evidence is consistent with a potential pressure anomaly."


def _valid_analysis(incident_id: str = _INCIDENT_ID) -> AIIncidentAnalysis:
    return AIIncidentAnalysis(
        incident_id=incident_id,
        summary=_SUMMARY,
        evidence_interpretation="Pressure deviation is consistent with a potential anomaly.",
        possible_causes=[
            PossibleCause(cause="Consistent with a potential pressure anomaly.", framing="consistent")
        ],
        investigation_actions=[
            {
                "action": "Verify the zone's pressure readings against the baseline.",
                "category": "evidence-verification",
                "priority": 1,
                "rationale": "Ground the next steps on the deterministic evidence.",
            }
        ],
        response_options=[
            ResponseOption(
                recommendation="An operator may verify the incident evidence.",
                priority=1,
                rationale="Assign the decision to a human operator.",
            )
        ],
        uncertainty=Uncertainty(supported=["Risk is 91.52."]),
        safety_notes=["Decision support only."],
    )


def orchestrator_source() -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "intelligence"
        / "ai_orchestrator.py"
    )
    return path.read_text(encoding="utf-8")


# --- result contract -----------------------------------------------------------


def test_analysis_source_enum_values():
    assert AnalysisSource.AI == "AI"
    assert AnalysisSource.FALLBACK == "FALLBACK"


def test_fallback_reason_enum_values():
    assert FallbackReason.PROVIDER_UNAVAILABLE == "PROVIDER_UNAVAILABLE"
    assert FallbackReason.PROVIDER_TIMEOUT == "PROVIDER_TIMEOUT"
    assert FallbackReason.MALFORMED_RESPONSE == "MALFORMED_RESPONSE"
    assert FallbackReason.INVALID_RESPONSE == "INVALID_RESPONSE"
    assert FallbackReason.PROVIDER_ERROR == "PROVIDER_ERROR"


def test_analysis_result_requires_valid_incident_id():
    result = AnalysisResult(
        incident_id=_INCIDENT_ID,
        source=AnalysisSource.FALLBACK,
        analysis=_valid_analysis(),
        ai_available=False,
        fallback_reason=FallbackReason.PROVIDER_UNAVAILABLE,
    )
    assert result.incident_id == _INCIDENT_ID
    with pytest.raises(Exception):
        AnalysisResult(
            incident_id="not-an-incident-id",
            source=AnalysisSource.FALLBACK,
            analysis=_valid_analysis(),
            ai_available=False,
            fallback_reason=FallbackReason.PROVIDER_UNAVAILABLE,
        )


# --- provider error mapping -> categorized fallback -----------------------------


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (ProviderUnavailableError("service down"), FallbackReason.PROVIDER_UNAVAILABLE),
        (ProviderTimeoutError("timed out"), FallbackReason.PROVIDER_TIMEOUT),
        (MalformedAIResponseError("not structured"), FallbackReason.MALFORMED_RESPONSE),
        (AIValidationError("validation failed"), FallbackReason.INVALID_RESPONSE),
        (AIProviderError("generic provider failure"), FallbackReason.PROVIDER_ERROR),
    ],
)
def test_provider_error_maps_to_categorized_fallback(error, expected_reason, golden_context):
    provider = StubProvider(error=error)
    result = AIOrchestrator(provider).analyze(golden_context)
    assert result.source is AnalysisSource.FALLBACK
    assert result.ai_available is False
    assert result.fallback_reason is expected_reason
    assert result.analysis.incident_id == golden_context.incident.incident_id


def test_lack_of_provider_gives_unavailable_fallback(golden_context, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = AIOrchestrator().analyze(golden_context)
    assert result.source is AnalysisSource.FALLBACK
    assert result.ai_available is False
    assert result.fallback_reason is FallbackReason.PROVIDER_UNAVAILABLE


def test_fallback_reason_is_safe_categorized_value(golden_context, caplog):
    secret = "abc123-secret-value"
    provider = StubProvider(error=ProviderUnavailableError(f"backend rejected token {secret}"))
    with caplog.at_level("WARNING"):
        result = AIOrchestrator(provider).analyze(golden_context)

    assert result.fallback_reason is FallbackReason.PROVIDER_UNAVAILABLE
    assert secret not in result.model_dump_json()
    assert secret not in caplog.text
    assert result.fallback_reason in {FallbackReason.PROVIDER_UNAVAILABLE}


# --- source attribution --------------------------------------------------------


def test_ai_success_sets_source_and_availability(golden_context):
    analysis = _valid_analysis(golden_context.incident.incident_id)
    provider = StubProvider(analysis=analysis)
    result = AIOrchestrator(provider).analyze(golden_context)
    assert result.source is AnalysisSource.AI
    assert result.ai_available is True
    assert result.fallback_reason is None
    assert result.incident_id == golden_context.incident.incident_id


def test_provider_analysis_passed_through_unchanged(golden_context):
    analysis = _valid_analysis(golden_context.incident.incident_id)
    provider = StubProvider(analysis=analysis)
    result = AIOrchestrator(provider).analyze(golden_context)
    assert result.analysis is analysis
    assert result.analysis.model_dump() == analysis.model_dump()


def test_incident_id_mismatch_falls_back_to_invalid_response(golden_context):
    analysis = _valid_analysis("INC-A-20260101T060000Z")
    provider = StubProvider(analysis=analysis)
    result = AIOrchestrator(provider).analyze(golden_context)
    assert result.source is AnalysisSource.FALLBACK
    assert result.ai_available is False
    assert result.fallback_reason is FallbackReason.INVALID_RESPONSE
    assert result.incident_id == golden_context.incident.incident_id


# --- unexpected errors propagate (never silent fallback) ------------------------


def test_unexpected_provider_error_propagates(golden_context):
    provider = StubProvider(error=RuntimeError("internal bug"))
    with pytest.raises(RuntimeError):
        AIOrchestrator(provider).analyze(golden_context)


def test_unexpected_default_factory_error_propagates(golden_context):
    def factory() -> None:
        raise TypeError("factory bug")

    with pytest.raises(TypeError):
        AIOrchestrator(default_provider_factory=factory).analyze(golden_context)


def test_analyze_rejects_non_context_input():
    with pytest.raises(TypeError):
        AIOrchestrator(StubProvider()).analyze(None)  # type: ignore[arg-type]


# --- deterministic fallback content --------------------------------------------


def test_fallback_summary_uses_context_values_only(golden_context):
    fallback = build_fallback_analysis(golden_context)
    summary = fallback.summary
    assert "Zone B" in summary or "zone B" in summary
    assert "CRITICAL" in summary
    assert "WATER_LOSS" not in summary
    assert f"{golden_context.risk.risk_score:.2f}" in summary


def test_fallback_evidence_lists_only_known_metrics(golden_context):
    known = {s.metric for s in golden_context.evidence.contributing_signals}
    fallback = build_fallback_analysis(golden_context)
    for signal in golden_context.evidence.contributing_signals:
        assert signal.metric in fallback.evidence_interpretation
    for token in ("flow_rate_vs_area", "temperature", "mystery_metric"):
        assert token not in fallback.evidence_interpretation
    assert f"{golden_context.evidence.evidence_score:.2f}" in fallback.evidence_interpretation
    assert f"{golden_context.evidence.persistence_minutes}" in fallback.evidence_interpretation
    assert f"{golden_context.evidence.citizen_report_count}" in fallback.evidence_interpretation


def test_fallback_does_not_invent_metrics_beyond_context():
    context = _make_context(metrics=["flow"])
    fallback = build_fallback_analysis(context)
    assert "flow" in fallback.evidence_interpretation
    assert "consumption" not in fallback.evidence_interpretation
    assert len(fallback.evidence_interpretation.splitlines()) == 2


def test_fallback_no_metric_signals_still_valid():
    context = _make_context(metrics=[])
    fallback = build_fallback_analysis(context)
    assert fallback.possible_causes
    assert "No metric-level contributing signals" in fallback.evidence_interpretation
    assert fallback.incident_id == _INCIDENT_ID


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_fallback_uses_per_type_cause_language(incident_type):
    context = _make_context(incident_type=incident_type)
    fallback = build_fallback_analysis(context)
    assert fallback.possible_causes
    assert _CAUSE_PHRASE[incident_type] in fallback.possible_causes[0].cause


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_fallback_investigation_actions_are_verify_inspect_compare(incident_type):
    fallback = build_fallback_analysis(_make_context(incident_type=incident_type))
    assert len(fallback.investigation_actions) == 3
    words = " ".join(
        action.action.lower() for action in fallback.investigation_actions
    )
    assert "verify" in words
    assert "inspect" in words
    assert "compare" in words
    assert [a.priority for a in fallback.investigation_actions] == [1, 2, 3]


def test_fallback_cause_framing_is_never_confirmed(golden_context):
    cause = build_fallback_analysis(golden_context).possible_causes[0]
    assert cause.framing == "consistent"
    lowered = cause.cause.lower()
    for banned in ("confirmed", "ruptured", "confirmed leak", "confirmed contamination"):
        assert banned not in lowered


def test_fallback_response_options_are_all_advisory(golden_context):
    options = build_fallback_analysis(golden_context).response_options
    assert options
    for option in options:
        assert isinstance(option, ResponseOption)
        assert option.advisory is True


def test_fallback_contains_no_autonomous_control_wording(golden_context):
    fallback = build_fallback_analysis(golden_context)
    combined = (
        fallback.summary
        + " ".join(c.cause for c in fallback.possible_causes)
        + " ".join(a.action for a in fallback.investigation_actions)
        + " ".join(o.recommendation for o in fallback.response_options)
        + " ".join(fallback.safety_notes)
    ).lower()
    for banned in _AUTONOMOUS_WORDS:
        assert banned not in combined


def test_fallback_has_structured_uncertainty(golden_context):
    uncertainty = build_fallback_analysis(golden_context).uncertainty
    assert isinstance(uncertainty, Uncertainty)
    assert uncertainty.supported
    assert uncertainty.uncertain
    assert uncertainty.additional_information


def test_fallback_has_safety_notes(golden_context):
    fallback = build_fallback_analysis(golden_context)
    assert fallback.safety_notes
    assert any("decision support" in note.lower() for note in fallback.safety_notes)
    assert any("operator" in note.lower() for note in fallback.safety_notes)
    assert any("advisory" in note.lower() for note in fallback.safety_notes)


# --- determinism ---------------------------------------------------------------


def test_fallback_is_deterministic_across_builds(golden_context):
    first = build_fallback_analysis(golden_context).model_dump()
    second = build_fallback_analysis(golden_context).model_dump()
    assert first == second


def test_fallback_is_deterministic_across_failure_modes(golden_context):
    unavailable = AIOrchestrator(
        StubProvider(error=ProviderUnavailableError())
    ).analyze(golden_context)
    timeout = AIOrchestrator(StubProvider(error=ProviderTimeoutError())).analyze(
        golden_context
    )
    assert unavailable.source is AnalysisSource.FALLBACK
    assert timeout.source is AnalysisSource.FALLBACK
    assert unavailable.analysis.model_dump() == timeout.analysis.model_dump()


# --- non-mutation --------------------------------------------------------------


def test_fallback_does_not_mutate_context(golden_context):
    before = golden_context.model_dump()
    AIOrchestrator(StubProvider(error=ProviderUnavailableError())).analyze(golden_context)
    assert golden_context.model_dump() == before


def test_ai_path_does_not_mutate_context(golden_context):
    analysis = _valid_analysis(golden_context.incident.incident_id)
    before = golden_context.model_dump()
    AIOrchestrator(StubProvider(analysis=analysis)).analyze(golden_context)
    assert golden_context.model_dump() == before


def test_analyze_incident_does_not_mutate_incident(golden_incident):
    before = dataclasses.asdict(golden_incident)
    result = analyze_incident(
        golden_incident,
        provider=StubProvider(error=ProviderUnavailableError()),
    )
    assert result.source is AnalysisSource.FALLBACK
    assert dataclasses.asdict(golden_incident) == before


# --- single attempt (no retry) -------------------------------------------------


def test_provider_invoked_exactly_once(golden_context):
    provider = StubProvider(error=ProviderUnavailableError())
    AIOrchestrator(provider).analyze(golden_context)
    assert provider.calls == 1


def test_default_provider_built_once(golden_context, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    calls = []

    def factory():
        calls.append(1)
        raise ProviderUnavailableError("no key")

    orchestrator = AIOrchestrator(default_provider_factory=factory)
    orchestrator.analyze(golden_context)
    orchestrator.analyze(golden_context)
    assert len(calls) == 1


# --- golden pipeline -----------------------------------------------------------


def test_golden_zone_b_ai_success(golden_context):
    analysis = _valid_analysis(golden_context.incident.incident_id)
    provider = StubProvider(analysis=analysis)
    result = AIOrchestrator(provider).analyze(golden_context)
    assert result.source is AnalysisSource.AI
    assert result.analysis.incident_id == golden_context.incident.incident_id


def test_golden_zone_b_fallback_preserves_deterministic_values(golden_context):
    provider = StubProvider(error=ProviderUnavailableError())
    result = AIOrchestrator(provider).analyze(golden_context)
    assert result.source is AnalysisSource.FALLBACK
    assert result.incident_id == golden_context.incident.incident_id
    summary = result.analysis.summary
    assert f"{golden_context.risk.risk_score:.2f}" in summary
    assert golden_context.incident.severity.value in summary
    assert f"{golden_context.incident.zone_id}" in summary
    assert len(result.analysis.evidence_interpretation.splitlines()) == 5
    for signal in golden_context.evidence.contributing_signals:
        assert signal.metric in result.analysis.evidence_interpretation


def test_golden_zone_b_fallback_deterministic_across_orchestrations(golden_context):
    first = AIOrchestrator(
        StubProvider(error=ProviderUnavailableError())
    ).analyze(golden_context)
    second = AIOrchestrator(
        StubProvider(error=ProviderTimeoutError())
    ).analyze(golden_context)
    assert first.analysis.model_dump() == second.analysis.model_dump()


# --- normal scenario (nothing to analyze) --------------------------------------

def test_normal_scenario_produces_no_incident_context():
    normal = run_simulation(build_config(seed=NORMAL_SEED))
    correlation = correlate_evidence(
        detect_anomalies(
            run_simulation(
                build_config(seed=REFERENCE_SEED, duration_hours=REFERENCE_DAYS * 24.0)
            ).measurements,
            normal.measurements,
        ),
        normal.reports,
    )
    assessments = assess_groups(correlation.groups, normal.zones)
    assert all(not a.qualified for a in assessments)
    assert not [a for a in assessments if a.qualified]


# --- source-level guarantees ---------------------------------------------------

@pytest.mark.parametrize("token", _FORBIDDEN_SOURCE_TOKENS)
def test_orchestrator_source_has_no_forbidden_coupling(token):
    source = orchestrator_source()
    assert token not in source