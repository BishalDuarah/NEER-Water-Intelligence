"""AI input context for the assistive AI layer (Phase 3-B1).

Builds a structured, minimized, deterministic ``IncidentAIContext`` from the
Phase 2C ``Incident`` for the FUTURE AI provider. Field names mirror the
deterministic models (``Incident``, ``RiskFactors``, ``ContributingSignal``,
``CorrelatedEvidenceGroup``) per ``docs/ai-context-contract.md``.

Ownership boundary (documented here, enforced by schema + tests):
- AUTHORITATIVE values (measurements, anomaly scores, evidence score,
  incident type, risk score, severity, confidence, timestamps, estimated
  population) are projected from the deterministic incident AS-IS. The AI
  layer may reference them but never recompute or override them.
- The context is incident-scoped and minimized: no unrelated zones/incidents,
  no raw sensor streams, no raw report bodies, no secrets/credentials, no
  DB/application internals.

This module is fully deterministic: no clocks, no randomness, no network, no
LLM, no database, no FastAPI. ``pydantic`` is used only as a schema/validation
boundary for the future provider input; the deterministic engines remain plain
frozen dataclasses.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.intelligence.correlation import CorrelatedEvidenceGroup
from app.intelligence.incident import (
    Incident,
    IncidentStatus,
    IncidentType,
    SeverityLabel,
    classification_support,
)

INCIDENT_ID_PATTERN = r"^INC-[A-Za-z0-9]+-\d{8}T\d{6}Z$"


class IncidentSection(BaseModel):
    """Deterministic incident metadata (authoritative projection)."""

    incident_id: str = Field(pattern=INCIDENT_ID_PATTERN)
    zone_id: str = Field(min_length=1)
    incident_type: IncidentType
    status: IncidentStatus
    severity: SeverityLabel
    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    start_time: datetime
    last_updated: datetime
    estimated_affected_population: int | None = Field(default=None, ge=0)


class ContributingSignalSummary(BaseModel):
    """Per-metric summary of the sensor evidence (not raw anomalies)."""

    metric: str = Field(min_length=1)
    direction: Literal["above", "below", "neutral"]
    anomaly_count: int = Field(ge=0)
    mean_z: float
    mean_abs_z: float = Field(ge=0.0)


class CitizenReportSummary(BaseModel):
    """Minimized citizen-context aggregation (no descriptions/PII)."""

    category: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    count: int = Field(ge=1)


class EvidenceSection(BaseModel):
    """Correlated-evidence statistics for the incident's zone."""

    contributing_signals: list[ContributingSignalSummary]
    signal_types: list[str] = Field(default_factory=list)
    evidence_score: float = Field(ge=0.0, le=1.0)
    temporal_coherence: float = Field(ge=0.0, le=1.0)
    spatial_coherence: float = Field(ge=0.0, le=1.0)
    signal_diversity: float = Field(ge=0.0, le=1.0)
    persistence_minutes: int = Field(ge=0)
    sensor_anomaly_count: int = Field(ge=0)
    citizen_report_count: int = Field(ge=0)
    citizen_report_summaries: list[CitizenReportSummary] = Field(default_factory=list)


class RiskSection(BaseModel):
    """Five normalized deterministic risk components (read-only references)."""

    evidence_strength: float = Field(ge=0.0, le=1.0)
    anomaly_severity: float = Field(ge=0.0, le=1.0)
    persistence: float = Field(ge=0.0, le=1.0)
    impact: float = Field(ge=0.0, le=1.0)
    citizen_context: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=100.0)


class ClassificationSection(BaseModel):
    """Deterministic classification with derived support."""

    incident_type: IncidentType
    classification_reason: str = Field(min_length=1)
    classification_support: float = Field(ge=0.0, le=1.0)


class IncidentAIContext(BaseModel):
    """Structured, minimized context consumed by the future AI provider."""

    incident: IncidentSection
    evidence: EvidenceSection
    risk: RiskSection
    classification: ClassificationSection


def _summarize_reports(
    reports: tuple | list,
) -> list[CitizenReportSummary]:
    counts = Counter((r.category, r.severity) for r in reports)
    return [
        CitizenReportSummary(category=category, severity=severity, count=count)
        for (category, severity), count in sorted(counts.items())
    ]


def _summarize_signals(
    incident: Incident,
) -> list[ContributingSignalSummary]:
    return [
        ContributingSignalSummary(
            metric=s.metric,
            direction=s.direction,
            anomaly_count=s.anomaly_count,
            mean_z=s.mean_z,
            mean_abs_z=s.mean_abs_z,
        )
        for s in incident.contributing_signals
    ]


def build_ai_context(
    incident: Incident,
    correlated_evidence: CorrelatedEvidenceGroup | None = None,
) -> IncidentAIContext:
    """Project a Phase 2C incident into an AI context (deterministic).

    ``correlated_evidence`` defaults to ``incident.evidence``; when supplied
    explicitly it takes precedence (same shape, incident-scoped). Nothing is
    invented: missing values stay missing (e.g. ``None`` population), never
    fabricated.
    """
    group = incident.evidence if correlated_evidence is None else correlated_evidence

    return IncidentAIContext(
        incident=IncidentSection(
            incident_id=incident.incident_id,
            zone_id=incident.zone_id,
            incident_type=incident.incident_type,
            status=incident.status,
            severity=incident.severity,
            risk_score=incident.risk_score,
            confidence=incident.confidence,
            start_time=incident.start_time,
            last_updated=incident.last_updated,
            estimated_affected_population=incident.estimated_affected_population,
        ),
        evidence=EvidenceSection(
            contributing_signals=_summarize_signals(incident),
            signal_types=list(group.signal_types),
            evidence_score=group.evidence_score,
            temporal_coherence=group.temporal_coherence,
            spatial_coherence=group.spatial_coherence,
            signal_diversity=group.signal_diversity,
            persistence_minutes=group.persistence_minutes,
            sensor_anomaly_count=group.sensor_anomaly_count,
            citizen_report_count=group.citizen_report_count,
            citizen_report_summaries=_summarize_reports(group.citizen_reports),
        ),
        risk=RiskSection(
            evidence_strength=incident.risk_factors.evidence_strength,
            anomaly_severity=incident.risk_factors.anomaly_severity,
            persistence=incident.risk_factors.persistence,
            impact=incident.risk_factors.impact,
            citizen_context=incident.risk_factors.citizen_context,
            risk_score=incident.risk_score,
        ),
        classification=ClassificationSection(
            incident_type=incident.incident_type,
            classification_reason=incident.classification_reason,
            classification_support=classification_support(group, incident.incident_type),
        ),
    )


def serialize_context(context: IncidentAIContext) -> str:
    """Canonical JSON serialization for future prompt construction.

    Deterministic (schema-ordered fields, sorted aggregations), JSON-compatible,
    and free of Python object reprs / secrets.
    """
    return context.model_dump_json()