"""NEER Water Intelligence - Phases 2A/2B/2C-B/3-A/3-B1/3-B2/3-B3: baseline,
anomaly detection, correlation, deterministic incident + risk assessment, the
AI context/output contract, the concrete Gemini provider, and AI orchestration
with a deterministic fallback.

Signal-level intelligence, evidence correlation, and incident assessment are
all deterministic and free of any LLM. Phase 3-B1 added the AI boundary models
and provider interface; Phase 3-B2 implements the concrete Gemini provider
behind that interface (SDK-backed, structured-output, network-bearing only when
a provider instance exists); Phase 3-B3 adds the orchestrator that gates AI
consumption and safely falls back to a deterministic analysis on failure.
"""

from app.intelligence.ai_analysis import (
    AIIncidentAnalysis,
    InvestigationAction,
    PossibleCause,
    ResponseOption,
    Uncertainty,
)
from app.intelligence.ai_context import (
    CitizenReportSummary,
    ClassificationSection,
    ContributingSignalSummary,
    EvidenceSection,
    IncidentAIContext,
    IncidentSection,
    RiskSection,
    build_ai_context,
    serialize_context,
)
from app.intelligence.ai_provider import (
    AIProvider,
    AIProviderError,
    AIValidationError,
    MalformedAIResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from app.intelligence.gemini_provider import (
    DEFAULT_MODEL,
    API_KEY_ENV,
    GeminiProvider,
    GeminiProviderConfig,
    SYSTEM_INSTRUCTIONS,
)
from app.intelligence.ai_orchestrator import (
    AIOrchestrator,
    AnalysisResult,
    AnalysisSource,
    FallbackReason,
    analyze_incident,
    build_fallback_analysis,
)
from app.intelligence.baseline import (
    BaselineConfig,
    BaselineSlot,
    build_baseline,
    bucket_label,
    bucket_of,
)
from app.intelligence.correlation import (
    CorrelateEngine,
    CorrelationConfig,
    CorrelationResult,
    CorrelatedEvidenceGroup,
    correlate_evidence,
)
from app.intelligence.detector import (
    STATUS_ANOMALOUS,
    STATUS_INSUFFICIENT,
    STATUS_INVALID,
    STATUS_NORMAL,
    AnomalyDetector,
    AnomalyResult,
    DetectorConfig,
    detect_anomalies,
)
from app.intelligence.incident import (
    Incident,
    IncidentAssessment,
    IncidentAssessor,
    IncidentConfig,
    IncidentStatus,
    IncidentType,
    RiskFactors,
    SeverityLabel,
    assess_group,
    assess_groups,
    classification_reason,
    classify_incident,
    compute_confidence,
    compute_risk_factors,
    compute_risk_score,
    severity_from_risk,
)

__all__ = [
    "API_KEY_ENV",
    "AIIncidentAnalysis",
    "AIOrchestrator",
    "AIProvider",
    "AIProviderError",
    "AIValidationError",
    "AnalysisResult",
    "AnalysisSource",
    "CitizenReportSummary",
    "ClassificationSection",
    "ContributingSignalSummary",
    "DEFAULT_MODEL",
    "EvidenceSection",
    "FallbackReason",
    "GeminiProvider",
    "GeminiProviderConfig",
    "IncidentAIContext",
    "IncidentSection",
    "InvestigationAction",
    "MalformedAIResponseError",
    "PossibleCause",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "ResponseOption",
    "RiskSection",
    "STATUS_ANOMALOUS",
    "SYSTEM_INSTRUCTIONS",
    "STATUS_INSUFFICIENT",
    "STATUS_INVALID",
    "STATUS_NORMAL",
    "AnomalyDetector",
    "AnomalyResult",
    "BaselineConfig",
    "BaselineSlot",
    "CorrelateEngine",
    "CorrelationConfig",
    "CorrelationResult",
    "CorrelatedEvidenceGroup",
    "DetectorConfig",
    "Incident",
    "IncidentAssessment",
    "IncidentAssessor",
    "IncidentConfig",
    "IncidentStatus",
    "IncidentType",
    "RiskFactors",
    "SeverityLabel",
    "Uncertainty",
    "assess_group",
    "assess_groups",
    "analyze_incident",
    "build_ai_context",
    "build_baseline",
    "build_fallback_analysis",
    "bucket_label",
    "bucket_of",
    "classification_reason",
    "classify_incident",
    "compute_confidence",
    "compute_risk_factors",
    "compute_risk_score",
    "correlate_evidence",
    "detect_anomalies",
    "serialize_context",
    "severity_from_risk",
]