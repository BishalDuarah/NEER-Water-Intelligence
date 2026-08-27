"""NEER Water Intelligence - Phase 2A/2B: baseline, anomaly detection, correlation.

Signal-level intelligence and evidence correlation only. Incident generation,
risk scoring, classification, and the AI layer are later phases and are NOT
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
    "build_baseline",
    "bucket_label",
    "bucket_of",
    "correlate_evidence",
    "detect_anomalies",
]