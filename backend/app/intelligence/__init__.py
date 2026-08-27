"""NEER Water Intelligence - Phase 2A: baseline + anomaly detection.

Signal-level intelligence only. Correlation, incident generation, risk
scoring, classification, and the AI layer are later phases and are NOT here.
"""

from app.intelligence.baseline import (
    BaselineConfig,
    BaselineSlot,
    build_baseline,
    bucket_label,
    bucket_of,
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
    "DetectorConfig",
    "build_baseline",
    "bucket_label",
    "bucket_of",
    "detect_anomalies",
]