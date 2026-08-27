"""NEER Water Intelligence - Phases 2A/2B/2C-B: baseline, anomaly detection,
correlation, and deterministic incident + risk assessment.

Signal-level intelligence, evidence correlation, and incident assessment are
all deterministic and free of any LLM. The AI layer is a later phase and is NOT
here.
"""

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
    "assess_group",
    "assess_groups",
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
    "severity_from_risk",
]