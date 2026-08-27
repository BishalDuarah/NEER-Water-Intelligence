"""Phase 3-C1 API schemas for the analysis endpoint.

These Pydantic models are the HTTP boundary of the analysis API. They wrap the
deterministic ``Incident``/``CorrelatedEvidenceGroup`` projections and the
``AnalysisResult`` produced by the intelligence layer into a compact, JSON-safe
shape. Clients never pass or receive raw domain objects, provider internals,
credentials, or stack traces.

The AI analysis is embedded by reusing the intelligence-layer
``AIIncidentAnalysis`` schema (the same validated shape the orchestrator
produces) — no duplication of the AI output contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.intelligence import (
    AIIncidentAnalysis,
    AnalysisSource,
    FallbackReason,
    IncidentStatus,
    IncidentType,
    SeverityLabel,
)


class AnalysisRunRequest(BaseModel):
    """Control parameters for one deterministic analysis run."""

    seed: int = Field(default=42, ge=0, le=100_000, description="Simulation random seed.")
    days: float = Field(
        default=1.0,
        gt=0,
        le=30.0,
        description="Number of simulated days to analyze (fractional allowed).",
    )
    scenario: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Registered simulation scenario id (e.g. ZONE_B_SUPPLY_INCIDENT).",
    )
    reference_seed: int = Field(
        default=99,
        ge=0,
        le=100_000,
        description="Seed of the reference (baseline) simulation window.",
    )


class ContributingSignalOut(BaseModel):
    """Per-metric summary of the sensor evidence (deterministic)."""

    metric: str
    direction: str
    anomaly_count: int
    mean_z: float
    mean_abs_z: float


class IncidentEvidenceOut(BaseModel):
    """Incident-scoped evidence summary (deterministic)."""

    contributing_signals: list[ContributingSignalOut]
    signal_types: list[str]
    evidence_score: float
    temporal_coherence: float
    spatial_coherence: float
    signal_diversity: float
    persistence_minutes: int
    sensor_anomaly_count: int
    citizen_report_count: int


class DeterministicIncidentOut(BaseModel):
    """Authoritative deterministic incident record (never AI-altered)."""

    incident_id: str
    zone_id: str
    incident_type: IncidentType
    status: IncidentStatus
    severity: SeverityLabel
    risk_score: float
    confidence: float
    start_time: datetime
    last_updated: datetime
    estimated_affected_population: int | None
    classification_reason: str
    explanation: str


class AIInfoOut(BaseModel):
    """AI attribution for one incident's analysis."""

    source: AnalysisSource
    ai_available: bool
    fallback_reason: FallbackReason | None


class AnalysisIncidentOut(BaseModel):
    """One fully assessed incident: deterministic record + evidence + AI output."""

    incident: DeterministicIncidentOut
    evidence: IncidentEvidenceOut
    ai: AIInfoOut
    analysis: AIIncidentAnalysis


class AnalysisRunMetadata(BaseModel):
    """Metadata about a single analysis execution."""

    run_id: str
    seed: int
    days: float
    scenario: str | None
    reference_seed: int
    data_source: Literal["deterministic-simulation"] = "deterministic-simulation"
    ran_at: datetime


class AnalysisRunSummary(BaseModel):
    """Compact summary of the analysis run."""

    incidents: int
    ai_source_count: int
    fallback_count: int
    zones: int
    window_hours: float


class AnalysisRunResponse(BaseModel):
    """Response of ``POST /api/v1/analysis/run``."""

    run: AnalysisRunMetadata
    incidents: list[AnalysisIncidentOut]
    summary: AnalysisRunSummary