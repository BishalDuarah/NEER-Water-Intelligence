"""AI orchestration & deterministic fallback (Phase 3-B3).

``AIOrchestrator`` is the single gate through which NEER consumes LLM output.
It turns ONE deterministic ``IncidentAIContext`` into ONE ``AnalysisResult``
by delegating to the injected ``AIProvider`` (the concrete Phase 3-B2 Gemini
provider by default) and failing SAFELY onto a fully deterministic fallback
analysis when the AI layer cannot produce a valid result.

Guarantees (enforced by this module + tests):

- the deterministic ``Incident`` and its values are never modified, overridden,
  or recomputed anywhere in this module;
- ``build_fallback_analysis`` is pure/deterministic: identical context produces
  byte-identical analysis, and it only references values already present in the
  context (no clocks live, no external-state reads, nothing network-bound);
- only ``AIProviderError`` subclasses trigger a fallback; any unexpected
  programming error propagates to the caller instead of being hidden;
- exactly one provider attempt is made (no retry loops);
- ``AnalysisResult.fallback_reason`` is a safe, categorized value (never a raw
  exception message), so no secret/provider internals can leak.

Ownership boundary: this module holds NO business logic that belongs to the
deterministic engines and performs NO autonomous control. All fallback wording
is qualified/advisory and mirrors the deterministic classification.
"""

from __future__ import annotations

import logging
from enum import Enum

from pydantic import BaseModel, Field

from app.intelligence.ai_analysis import (
    AIIncidentAnalysis,
    InvestigationAction,
    PossibleCause,
    ResponseOption,
    Uncertainty,
)
from app.intelligence.ai_context import (
    INCIDENT_ID_PATTERN,
    IncidentAIContext,
    build_ai_context,
)
from app.intelligence.ai_provider import (
    AIProvider,
    AIProviderError,
    AIValidationError,
    MalformedAIResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.intelligence.correlation import CorrelatedEvidenceGroup
from app.intelligence.incident import Incident, IncidentType

logger = logging.getLogger(__name__)


class AnalysisSource(str, Enum):
    """Where the returned analysis came from."""

    AI = "AI"
    FALLBACK = "FALLBACK"


class FallbackReason(str, Enum):
    """Safe, categorized reason for using the deterministic fallback."""

    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class AnalysisResult(BaseModel):
    """Outcome of an AI analysis attempt for one incident."""

    incident_id: str = Field(pattern=INCIDENT_ID_PATTERN)
    source: AnalysisSource
    analysis: AIIncidentAnalysis
    ai_available: bool
    fallback_reason: FallbackReason | None = None


def _reason_for(error: AIProviderError) -> FallbackReason:
    """Map a provider error onto the safe fallback-reason vocabulary."""
    if isinstance(error, ProviderUnavailableError):
        return FallbackReason.PROVIDER_UNAVAILABLE
    if isinstance(error, ProviderTimeoutError):
        return FallbackReason.PROVIDER_TIMEOUT
    if isinstance(error, MalformedAIResponseError):
        return FallbackReason.MALFORMED_RESPONSE
    if isinstance(error, AIValidationError):
        return FallbackReason.INVALID_RESPONSE
    return FallbackReason.PROVIDER_ERROR


def _humanize_type(incident_type: IncidentType) -> str:
    if incident_type is IncidentType.UNKNOWN:
        return "incident"
    return incident_type.value.replace("_", " ").title()


# --------------------------------------------------------------------------- #
# Deterministic fallback templates (Phase 3-B3).
#
# All wording is qualified and advisory: causes are "potential/consistent",
# actions "verify/inspect/compare", response options advisory. The templates
# never assert a confirmed physical failure and never imply autonomous control.
# --------------------------------------------------------------------------- #


def _cause_template(incident_type: IncidentType) -> str:
    if incident_type is IncidentType.WATER_LOSS:
        return (
            "The pattern of deviations is consistent with a potential water loss "
            "event that could reduce available supply in the zone."
        )
    if incident_type is IncidentType.WATER_QUALITY:
        return (
            "The pattern of deviations is consistent with a potential water "
            "quality issue affecting the zone."
        )
    if incident_type is IncidentType.PRESSURE_ANOMALY:
        return (
            "The pattern of deviations is consistent with a potential pressure "
            "anomaly affecting the zone."
        )
    if incident_type is IncidentType.SUPPLY_DISRUPTION:
        return (
            "The pattern of deviations is consistent with a potential supply "
            "disruption affecting the zone."
        )
    return "Available evidence does not support a sufficiently specific incident cause."


_INVESTIGATION_ACTIONS: dict[IncidentType, tuple[tuple[str, str, str], ...]] = {
    IncidentType.WATER_LOSS: (
        (
            "Verify the zone's pressure, flow, and consumption readings against "
            "the historical baseline before any field action.",
            "evidence-verification",
            "Grounds the next steps on the deterministic baseline evidence.",
        ),
        (
            "Inspect the zone's network for visible signs consistent with a "
            "potential water loss event (for example wet patches or "
            "low-pressure reports).",
            "physical-inspection",
            "Confirms or rules out a visible water loss signature in the field.",
        ),
        (
            "Compare this zone's readings with neighboring zones to bound the "
            "potential affected area.",
            "spatial-comparison",
            "Helps determine whether the signal is localized to this zone.",
        ),
    ),
    IncidentType.WATER_QUALITY: (
        (
            "Verify the zone's latest sensor readings (including any quality "
            "metrics) against the historical baseline.",
            "evidence-verification",
            "Grounds the next steps on the deterministic baseline evidence.",
        ),
        (
            "Inspect sampling and treatment points in the zone for conditions "
            "consistent with a potential water quality issue.",
            "physical-inspection",
            "Confirms or rules out a water quality source in the field.",
        ),
        (
            "Compare this zone's readings with neighboring zones to determine "
            "whether the signal is localized.",
            "spatial-comparison",
            "Helps determine the extent of the potential issue.",
        ),
    ),
    IncidentType.PRESSURE_ANOMALY: (
        (
            "Verify the zone's pressure readings against the historical baseline "
            "and confirm the anomaly duration.",
            "evidence-verification",
            "Grounds the next steps on the deterministic baseline evidence.",
        ),
        (
            "Inspect pressure-regulating assets (valves and pumps) in the zone "
            "for conditions consistent with a potential pressure anomaly.",
            "physical-inspection",
            "Confirms or rules out a pressure control issue in the field.",
        ),
        (
            "Compare this zone's pressure readings with neighboring zones to "
            "identify the affected region.",
            "spatial-comparison",
            "Helps determine whether the anomaly is localized to this zone.",
        ),
    ),
    IncidentType.SUPPLY_DISRUPTION: (
        (
            "Verify the zone's flow, consumption, and complaint data against "
            "the historical baseline to confirm the disruption window.",
            "evidence-verification",
            "Grounds the next steps on the deterministic baseline evidence.",
        ),
        (
            "Inspect the zone's supply configuration for conditions consistent "
            "with a potential supply disruption.",
            "physical-inspection",
            "Confirms or rules out a supply configuration issue in the field.",
        ),
        (
            "Compare this zone's status with neighboring zones to determine "
            "whether the disruption is localized.",
            "spatial-comparison",
            "Helps determine the extent of the potential disruption.",
        ),
    ),
    IncidentType.UNKNOWN: (
        (
            "Verify the zone's recent sensor readings against the historical "
            "baseline to confirm the detected deviations.",
            "evidence-verification",
            "Grounds the next steps on the deterministic baseline evidence.",
        ),
        (
            "Inspect the zone for visible signs or recent activity consistent "
            "with the detected deviations.",
            "physical-inspection",
            "Confirms or rules out an observable field signature.",
        ),
        (
            "Compare this zone's readings with neighboring zones to determine "
            "whether the signal is localized.",
            "spatial-comparison",
            "Helps determine whether the deviation is incident-scoped.",
        ),
    ),
}


def _interpret_evidence(context: IncidentAIContext) -> str:
    lines = [
        f"- {s.metric}: {s.anomaly_count} detected anomaly(-ies) with mean "
        f"absolute deviation {s.mean_abs_z:.2f} ({s.direction} of baseline)."
        for s in context.evidence.contributing_signals
    ]
    if not lines:
        lines = ["- No metric-level contributing signals were summarized in the context."]
    lines.append(
        f"Overall: deterministic evidence score {context.evidence.evidence_score:.2f}, "
        f"signal diversity {context.evidence.signal_diversity:.2f}, "
        f"{context.evidence.persistence_minutes} minutes persistence, "
        f"{context.evidence.citizen_report_count} citizen report(s) considered."
    )
    return "\n".join(lines)


def build_fallback_analysis(context: IncidentAIContext) -> AIIncidentAnalysis:
    """Build a validated, fully deterministic analysis from the context alone.

    Only uses values already present in ``context``; identical inputs produce
    identical output. This is what NEER surfaces when the AI layer is not
    available or fails.
    """
    incident = context.incident
    evidence = context.evidence
    risk = context.risk

    type_title = _humanize_type(incident.incident_type)
    summary = (
        f"The incident in zone {incident.zone_id} is classified as a potential "
        f"{type_title} event with {incident.severity.value} severity and a "
        f"deterministic risk score of {risk.risk_score:.2f}."
    )

    supporting_evidence = [
        f"{len(evidence.contributing_signals)} contributing signal(s) in the zone",
        f"evidence score {evidence.evidence_score:.2f}",
        f"{evidence.sensor_anomaly_count} sensor anomalies",
    ]

    possible_causes = [
        PossibleCause(
            cause=_cause_template(incident.incident_type),
            framing="consistent",
            supporting_evidence=supporting_evidence,
        )
    ]

    type_name = incident.incident_type
    investigation_actions = [
        InvestigationAction(
            action=action_text,
            category=category,
            priority=index + 1,
            rationale=rationale,
        )
        for index, (action_text, category, rationale) in enumerate(
            _INVESTIGATION_ACTIONS.get(type_name, _INVESTIGATION_ACTIONS[IncidentType.UNKNOWN])
        )
    ]

    response_options = [
        ResponseOption(
            recommendation=(
                "Consider increasing monitoring frequency in this zone while "
                "the incident remains open."
            ),
            priority=1,
            rationale="Keeps the deterministic evidence under observation.",
        ),
        ResponseOption(
            recommendation=(
                "An operator may verify the evidence and update the incident "
                "assessment."
            ),
            priority=2,
            rationale="Assigns the next decision to a human operator.",
        ),
        ResponseOption(
            recommendation=(
                "Consider notifying the relevant operations team about this "
                "incident to coordinate a manual field check."
            ),
            priority=3,
            rationale="Escalates to the team responsible for field operations.",
        ),
    ]

    uncertainty = Uncertainty(
        supported=[
            (
                f"Classification is {incident.incident_type.value} with "
                f"deterministic support {context.classification.classification_support:.2f}."
            ),
            f"{evidence.sensor_anomaly_count} sensor anomalies were detected in this zone.",
            f"The deterministic evidence score is {evidence.evidence_score:.2f}.",
            f"Risk is {risk.risk_score:.2f} with {incident.severity.value} severity.",
        ],
        uncertain=[
            "Physical root cause of the deviation.",
            "Exact location of any failure within the zone.",
            (
                "Whether the signal originates from operational infrastructure "
                "or from instrumentation."
            ),
        ],
        additional_information=[
            "Field verification by an operator.",
            "Validation of the affected sensors.",
            "Readings from neighboring zones.",
            "Operational or maintenance records for the zone.",
        ],
    )

    safety_notes = [
        (
            "Decision support only: this analysis recommends, it never controls "
            "water infrastructure automatically."
        ),
        (
            "The physical cause is not confirmed; operator verification is "
            "required before any field action."
        ),
        (
            "Recommendations are advisory and must be executed only by "
            "authorized personnel."
        ),
    ]

    return AIIncidentAnalysis(
        incident_id=incident.incident_id,
        summary=summary,
        evidence_interpretation=_interpret_evidence(context),
        possible_causes=possible_causes,
        investigation_actions=investigation_actions,
        response_options=response_options,
        uncertainty=uncertainty,
        safety_notes=safety_notes,
    )


class AIOrchestrator:
    """Coordinates one AI analysis attempt with a deterministic fallback.

    A provider may be injected directly (as in tests). Otherwise a default
    provider is built lazily from ``default_provider_factory`` (the concrete
    Phase 3-B2 Gemini provider). Laziness keeps construction of ``AIOrchestrator``
    free of SDK imports and network I/O; a missing ``GEMINI_API_KEY`` surfaces as
    a deterministic ``PROVIDER_UNAVAILABLE`` fallback, never an import error.
    """

    def __init__(
        self,
        provider: AIProvider | None = None,
        *,
        default_provider_factory: callable | None = None,
    ) -> None:
        self._provider = provider
        self._default_provider_factory = default_provider_factory
        self._default_state: tuple[AIProvider | None, FallbackReason | None] | None = None

    @staticmethod
    def _build_default_provider() -> AIProvider:
        from app.intelligence.gemini_provider import GeminiProvider

        return GeminiProvider()

    def _resolve_provider(self) -> tuple[AIProvider | None, FallbackReason | None]:
        if self._provider is not None:
            return self._provider, None
        if self._default_state is not None:
            return self._default_state
        factory = self._default_provider_factory or self._build_default_provider
        try:
            provider = factory()
        except AIProviderError:
            self._default_state = (None, FallbackReason.PROVIDER_UNAVAILABLE)
            return self._default_state
        if provider is None:
            self._default_state = (None, FallbackReason.PROVIDER_UNAVAILABLE)
            return self._default_state
        self._default_state = (provider, None)
        return self._default_state

    @staticmethod
    def _log_fallback(incident_id: str, reason: FallbackReason | None) -> None:
        logger.warning(
            "AI incident analysis unavailable for incident %s; using "
            "deterministic fallback (reason=%s).",
            incident_id,
            reason.value if reason is not None else "unknown",
        )

    @staticmethod
    def _build_fallback_result(
        context: IncidentAIContext,
        reason: FallbackReason,
    ) -> AnalysisResult:
        return AnalysisResult(
            incident_id=context.incident.incident_id,
            source=AnalysisSource.FALLBACK,
            analysis=build_fallback_analysis(context),
            ai_available=False,
            fallback_reason=reason,
        )

    def analyze(self, context: IncidentAIContext) -> AnalysisResult:
        """Analyze ``context`` exactly once, falling back deterministically.

        Only ``AIProviderError`` subclasses trigger a fallback; the incident id
        returned by the provider is re-verified against the context. Any other
        unexpected error propagates to the caller. ``context`` is never mutated.
        """
        if not isinstance(context, IncidentAIContext):
            raise TypeError("analyze expects an IncidentAIContext, got %s" % type(context).__name__)
        incident_id = context.incident.incident_id

        provider, reason = self._resolve_provider()
        if provider is None:
            self._log_fallback(incident_id, reason)
            return self._build_fallback_result(context, reason)

        try:
            analysis = provider.generate_analysis(context)
        except AIProviderError as error:
            reason = _reason_for(error)
            self._log_fallback(incident_id, reason)
            return self._build_fallback_result(context, reason)

        if not isinstance(analysis, AIIncidentAnalysis) or analysis.incident_id != incident_id:
            reason = FallbackReason.INVALID_RESPONSE
            self._log_fallback(incident_id, reason)
            return self._build_fallback_result(context, reason)

        return AnalysisResult(
            incident_id=incident_id,
            source=AnalysisSource.AI,
            analysis=analysis,
            ai_available=True,
            fallback_reason=None,
        )


def analyze_incident(
    incident: Incident,
    correlated_evidence: CorrelatedEvidenceGroup | None = None,
    provider: AIProvider | None = None,
) -> AnalysisResult:
    """Convenience wrapper: project ``incident`` then analyze it once.

    Equivalent to ``AIOrchestrator(provider).analyze(build_ai_context(...))``.
    """
    context = build_ai_context(incident, correlated_evidence)
    return AIOrchestrator(provider).analyze(context)