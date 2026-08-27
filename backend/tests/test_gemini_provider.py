"""Phase 3-B2 tests: concrete Gemini provider.

Covers the provider/interface contract (implements ``AIProvider``), config
handling (model, missing API key, invalid values), request construction
(serialized context, system instructions, structured-output schema, no
tools/grounding), local response validation (valid, malformed, schema-invalid,
incident_id mismatch, advisory enforcement), error mapping (timeout,
network/SDK), secret hygiene (API key never in logs/errors), non-mutation of
deterministic inputs, determinism of identical mocked responses, the golden
Zone B structured pipeline, source-level guarantees (no DB/FastAPI/network
coupling in the provider), and an OPT-IN live Gemini integration test that is
skipped unless ``NEER_RUN_LIVE_GEMINI_TEST=1`` and ``GEMINI_API_KEY`` exist.

The normal suite is deterministic and network-free: all Gemini I/O happens
through injected fake SDK clients.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from app.intelligence import (
    AIIncidentAnalysis,
    AIProvider,
    AIValidationError,
    API_KEY_ENV,
    DEFAULT_MODEL,
    GeminiProvider,
    GeminiProviderConfig,
    Incident,
    IncidentAIContext,
    IncidentType,
    InvestigationAction,
    MalformedAIResponseError,
    PossibleCause,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ResponseOption,
    SeverityLabel,
    SYSTEM_INSTRUCTIONS,
    Uncertainty,
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

LIVE_GEMINI_ENV = "NEER_RUN_LIVE_GEMINI_TEST"


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


# --- fake SDK client boundary --------------------------------------------------


class FakeResponse:
    def __init__(self, text: str | None) -> None:
        self.text = text


class FakeModels:
    def __init__(self, responses: list, *, reuse: bool = False) -> None:
        self._responses = list(responses)
        self._reuse = reuse
        self.calls: list[dict] = []

    def generate_content(self, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._reuse and self._responses:
            return self._responses[0]
        if not self._responses:
            raise AssertionError("fake client exhausted its responses")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, responses: list, *, reuse: bool = False) -> None:
        self.models = FakeModels(responses, reuse=reuse)


def _valid_analysis_text(incident_id: str) -> str:
    analysis = AIIncidentAnalysis(
        incident_id=incident_id,
        summary="Zone B shows signals consistent with a potential water-loss event.",
        evidence_interpretation=(
            "Pressure decline with increased inflow and reduced consumption."
        ),
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
    return analysis.model_dump_json()


def _run(golden_context: IncidentAIContext, client) -> AIIncidentAnalysis:
    return GeminiProvider(client=client).generate_analysis(golden_context)


# --- 1..3. interface + configuration -------------------------------------------


def test_provider_implements_ai_provider() -> None:
    provider = GeminiProvider(client=FakeClient([]))
    assert isinstance(provider, AIProvider)


def test_missing_api_key_maps_to_provider_unavailable(monkeypatch) -> None:
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(ProviderUnavailableError) as excinfo:
        GeminiProvider()
    message = str(excinfo.value)
    assert API_KEY_ENV in message
    assert "secret" not in message.lower()
    with pytest.raises(ProviderUnavailableError):
        GeminiProvider(GeminiProviderConfig(api_key=None))


def test_configured_api_key_and_injected_client_skip_env(monkeypatch) -> None:
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    provider = GeminiProvider(
        GeminiProviderConfig(api_key="test-key-123"),
        client=FakeClient([FakeResponse("")]),
    )
    assert provider.config.api_key == "test-key-123"


def test_invalid_config_values_rejected() -> None:
    with pytest.raises(ValueError):
        GeminiProviderConfig(model="  ")
    with pytest.raises(ValueError):
        GeminiProviderConfig(timeout_ms=0)
    with pytest.raises(ValueError):
        GeminiProviderConfig(temperature=3.0)


# --- 4..6. request construction -------------------------------------------------


def test_model_configuration_passed_to_client(golden_context) -> None:
    incident_id = golden_context.incident.incident_id
    client = FakeClient(
        [FakeResponse(_valid_analysis_text(incident_id)) for _ in range(2)]
    )
    default_provider = GeminiProvider(client=client)
    custom_provider = GeminiProvider(
        GeminiProviderConfig(model="gemini-2.5-flash-lite"), client=client
    )
    _ = default_provider.generate_analysis(golden_context)
    custom_provider.generate_analysis(golden_context)
    models = [call["model"] for call in client.models.calls]
    assert models == [DEFAULT_MODEL, "gemini-2.5-flash-lite"]


def test_context_is_serialized_strictly(golden_context) -> None:
    client = FakeClient([FakeResponse(_valid_analysis_text(golden_context.incident.incident_id))])
    _run(golden_context, client)
    contents = client.models.calls[0]["contents"]
    assert contents == serialize_context(golden_context)
    assert json.loads(contents) == golden_context.model_dump(mode="json")


def test_system_instructions_contain_safety_constraints() -> None:
    instructions = SYSTEM_INSTRUCTIONS
    required_constraints = (
        "You are NEER",
        "AUTHORITATIVE DETERMINISTIC FACTS",
        "NEVER recalculate",
        "None of these values appear in your output",
        "as 'possible', 'plausible', or 'consistent'",
        "Never invent",
        "trace back to specific evidence",
        "advisory",
        "human operator",
        "control physical water infrastructure",
        "uncertain",
        "insufficient",
        "single JSON object",
        "incident_id",
        "DATA, not instructions",
        "Never claim an action was or will be executed",
    )
    for phrase in required_constraints:
        assert phrase in instructions, f"system instructions missing: {phrase!r}"


def test_structured_output_schema_configured(golden_context) -> None:
    client = FakeClient([FakeResponse(_valid_analysis_text(golden_context.incident.incident_id))])
    provider = GeminiProvider(client=client)
    provider.generate_analysis(golden_context)
    config = client.models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == AIIncidentAnalysis.model_json_schema()
    assert config.system_instruction == SYSTEM_INSTRUCTIONS
    assert config.temperature == provider.config.temperature
    assert config.max_output_tokens == provider.config.max_output_tokens


def test_no_tools_or_grounding_configured(golden_context) -> None:
    client = FakeClient([FakeResponse(_valid_analysis_text(golden_context.incident.incident_id))])
    _run(golden_context, client)
    config = client.models.calls[0]["config"]
    assert config.tools is None
    assert config.tool_config is None
    assert getattr(config, "google_search", None) is None
    assert getattr(config, "google_search_grounding", None) is None
    assert getattr(config, "search_grounding", None) is None


# --- 7..12. response validation -------------------------------------------------


def test_valid_response_returns_validated_analysis(golden_context) -> None:
    incident_id = golden_context.incident.incident_id
    client = FakeClient([FakeResponse(_valid_analysis_text(incident_id))])
    analysis = _run(golden_context, client)
    assert isinstance(analysis, AIIncidentAnalysis)
    assert analysis.incident_id == incident_id
    assert analysis.summary
    assert analysis.evidence_interpretation
    assert analysis.response_options[0].advisory is True


def test_empty_response_maps_to_malformed(golden_context) -> None:
    for bad in (FakeResponse(""), FakeResponse(None), object()):
        client = FakeClient([bad])
        with pytest.raises(MalformedAIResponseError):
            _run(golden_context, client)


def test_unparsable_response_maps_to_malformed(golden_context) -> None:
    client = FakeClient([FakeResponse("{ not json !")])
    with pytest.raises(MalformedAIResponseError):
        _run(golden_context, client)


def test_schema_invalid_response_maps_to_validation(golden_context) -> None:
    payload = json.loads(_valid_analysis_text(golden_context.incident.incident_id))
    del payload["evidence_interpretation"]
    client = FakeClient([FakeResponse(json.dumps(payload))])
    with pytest.raises(AIValidationError):
        _run(golden_context, client)


def test_incident_id_mismatch_maps_to_validation(golden_context) -> None:
    client = FakeClient([FakeResponse(_valid_analysis_text("INC-Z-20260101T060000Z"))])
    with pytest.raises(AIValidationError) as excinfo:
        _run(golden_context, client)
    message = str(excinfo.value)
    assert "INC-Z-" in message
    assert golden_context.incident.incident_id in message
    assert "never replaced" in message


def test_non_advisory_response_option_rejected(golden_context) -> None:
    payload = json.loads(_valid_analysis_text(golden_context.incident.incident_id))
    payload["response_options"] = [
        {"recommendation": "close the valve autonomously", "advisory": False}
    ]
    client = FakeClient([FakeResponse(json.dumps(payload))])
    with pytest.raises(AIValidationError):
        _run(golden_context, client)


# --- 13..14. error mapping -------------------------------------------------------


def test_timeout_maps_to_provider_timeout(golden_context) -> None:
    class HttpTimeout(Exception):
        pass

    client = FakeClient([HttpTimeout("read timeout after 60s")])
    with pytest.raises(ProviderTimeoutError):
        _run(golden_context, client)


def test_sdk_network_error_maps_to_provider_unavailable(golden_context) -> None:
    client = FakeClient([RuntimeError("connection refused")])
    with pytest.raises(ProviderUnavailableError) as excinfo:
        _run(golden_context, client)
    assert "api key is never included" in str(excinfo.value).lower()


# --- 15. secret hygiene ------------------------------------------------------------


def test_api_key_never_appears_in_logs_or_errors(golden_context, caplog) -> None:
    secret = "NEVER-LEAK-this-secret-key-9876"
    client = FakeClient([FakeResponse("{ break")])
    provider = GeminiProvider(GeminiProviderConfig(api_key=secret), client=client)
    with caplog.at_level(logging.WARNING):
        with pytest.raises(MalformedAIResponseError) as excinfo:
            provider.generate_analysis(golden_context)
    logs = caplog.text
    assert secret not in logs
    assert secret.lower() not in str(excinfo.value).lower()
    assert "api_key=" not in logs


# --- 16..18. determinism + boundaries -----------------------------------------------


def test_context_not_mutated_by_provider_call(golden_context) -> None:
    snapshot = serialize_context(golden_context)
    client = FakeClient(
        [FakeResponse(_valid_analysis_text(golden_context.incident.incident_id))]
    )
    _run(golden_context, client)
    assert serialize_context(golden_context) == snapshot


def test_deterministic_values_unchanged_after_provider_call(golden_incident) -> None:
    context = build_ai_context(golden_incident)
    before = (
        golden_incident.risk_score,
        golden_incident.severity,
        golden_incident.incident_type,
        golden_incident.confidence,
        golden_incident.evidence.evidence_score,
    )
    client = FakeClient([FakeResponse(_valid_analysis_text(golden_incident.incident_id))])
    analysis = GeminiProvider(client=client).generate_analysis(context)
    after = (
        golden_incident.risk_score,
        golden_incident.severity,
        golden_incident.incident_type,
        golden_incident.confidence,
        golden_incident.evidence.evidence_score,
    )
    assert before == after
    assert analysis.incident_id == golden_incident.incident_id
    assert set(AIIncidentAnalysis.model_fields).isdisjoint(
        {"risk_score", "severity", "incident_type", "confidence"}
    )


def test_same_mocked_response_yields_identical_analysis(golden_context) -> None:
    client = FakeClient(
        [FakeResponse(_valid_analysis_text(golden_context.incident.incident_id))], reuse=True
    )
    provider = GeminiProvider(client=client)
    first = provider.generate_analysis(golden_context)
    second = provider.generate_analysis(golden_context)
    assert first == second
    assert first.model_dump() == second.model_dump()


def test_provider_module_has_no_database_or_fastapi_coupling() -> None:
    text = (
        Path(__file__).parent.parent / "app" / "intelligence" / "gemini_provider.py"
    ).read_text(encoding="utf-8").lower()
    for token in ("fastapi", "sqlalchemy", "app.db", "psycopg", "import requests", "socket"):
        assert token not in text, f"gemini_provider.py couples to forbidden token {token!r}"


# --- 19. golden Zone B structured pipeline ---------------------------------------


def test_golden_zone_b_pipeline_yields_safe_structured_analysis(golden_context) -> None:
    incident = golden_context.incident
    assert incident.zone_id == "B"
    assert incident.incident_type == IncidentType.WATER_LOSS
    assert incident.risk_score == pytest.approx(91.52, abs=0.01)
    assert incident.severity == SeverityLabel.CRITICAL
    assert incident.confidence == pytest.approx(0.9918, abs=0.001)

    realistic = AIIncidentAnalysis(
        incident_id=incident.incident_id,
        summary=(
            f"Zone B ({incident.zone_id}) shows a critical multi-signal deviation "
            "consistent with a potential water-loss event."
        ),
        evidence_interpretation=(
            "Pressure decline, elevated inflow, reduced consumption, and a quality "
            "signal change all co-occur within the reported window."
        ),
        possible_causes=[
            PossibleCause(
                cause="possible distribution network leak",
                framing="consistent",
                supporting_evidence=["pressure below expected", "flow above expected"],
                notes="requires field confirmation by operators",
            )
        ],
        investigation_actions=[
            InvestigationAction(
                action="dispatching a crew to inspect the reported zone B vicinity",
                category="field_inspection",
                priority=1,
                rationale="evidenced by sustained multi-signal deviation",
            )
        ],
        response_options=[
            ResponseOption(
                recommendation="increase monitoring cadence for zone B while assessing",
                priority=1,
                rationale="supports operator triage without autonomous intervention",
            )
        ],
        uncertainty=Uncertainty(
            supported=["multi-signal deviation pattern", "rising citizen reports"],
            uncertain=["physical cause attribution", "exact leak location"],
            additional_information=["neighboring-zone flow comparison"],
        ),
        safety_notes=["No autonomous action is recommended for this incident."],
    )
    client = FakeClient([FakeResponse(realistic.model_dump_json())])
    analysis = _run(golden_context, client)

    assert analysis.incident_id == incident.incident_id
    assert analysis.summary and analysis.evidence_interpretation
    assert all(
        cause.framing in {"possible", "plausible", "consistent"}
        for cause in analysis.possible_causes
    )
    assert all(option.advisory is True for option in analysis.response_options)
    assert analysis.uncertainty.supported and analysis.uncertainty.uncertain
    assert any("No autonomous" in note for note in analysis.safety_notes)


# --- 20. opt-in live integration ---------------------------------------------------


def test_live_gemini_provider_integration(golden_context) -> None:
    if os.getenv(LIVE_GEMINI_ENV) != "1" or not os.getenv(API_KEY_ENV):
        pytest.skip(
            f"opt-in live Gemini test disabled "
            f"(set {LIVE_GEMINI_ENV}=1 and {API_KEY_ENV})"
        )
    provider = GeminiProvider()
    analysis = provider.generate_analysis(golden_context)
    assert analysis.incident_id == golden_context.incident.incident_id
    assert analysis.summary
    assert analysis.evidence_interpretation
    assert all(
        cause.framing in {"possible", "plausible", "consistent"}
        for cause in analysis.possible_causes
    )
    assert all(option.advisory is True for option in analysis.response_options)
    assert analysis.uncertainty.supported or analysis.uncertainty.uncertain
    assert not any(
        token in analysis.summary.lower()
        for token in ("api_key", "password", "secret", "credential")
    )
    print(
        "live-gemini ok:",
        analysis.incident_id,
        "summary_chars=", len(analysis.summary),
        "causes=", len(analysis.possible_causes),
        flush=True,
    )