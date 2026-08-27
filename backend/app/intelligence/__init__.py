"""NEER Water Intelligence - Phases 2A/2B/2C-B/3-B1: baseline, anomaly
detection, correlation, deterministic incident + risk assessment, and the AI
context/output contract.

Signal-level intelligence, evidence correlation, and incident assessment are
all deterministic and free of any LLM. Phase 3-B1 adds the AI boundary models
and provider interface (still no LLM calls, no provider implementation).
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
    "AIIncidentAnalysis",
    "AIProvider",
    "AIProviderError",
    "AIValidationError",
    "CitizenReportSummary",
    "ClassificationSection",
    "ContributingSignalSummary",
    "EvidenceSection",
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
    "build_ai_context",
    "build_baseline",
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