"""Phase 3-C1 application service: deterministic analysis execution.

``AnalysisService`` is the adapter that runs the existing deterministic
intelligence pipeline (simulation -> anomaly detection -> correlation ->
incident/risk assessment) and asks the injected ``AIOrchestrator`` for an AI
explanation of each qualified incident. It holds NO anomaly/correlation/risk
formulas and NO AI fallback logic — those live in the locked intelligence
modules and are reused as-is.

FastAPI never calls the pipeline directly: HTTP routes depend on this service,
and the service depends on the orchestrator (which may be injected for tests).

The reference window is a fixed 7-day baseline (``REFERENCE_WINDOW_DAYS``),
matching the convention used across the locked intelligence test suite: a week
of time-of-day baseline data against which the target window is scored.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.intelligence import (
    AIOrchestrator,
    AnalysisResult,
    AnalysisSource,
    Incident,
    correlate_evidence,
    detect_anomalies,
    assess_groups,
    build_ai_context,
)
from app.schemas.analysis import (
    AIInfoOut,
    AnalysisIncidentOut,
    AnalysisRunMetadata,
    AnalysisRunRequest,
    AnalysisRunResponse,
    AnalysisRunSummary,
    ContributingSignalOut,
    DeterministicIncidentOut,
    IncidentEvidenceOut,
)
from app.simulation import SCENARIOS, build_config, run_simulation

REFERENCE_WINDOW_DAYS = 7.0


class AnalysisServiceError(Exception):
    """Base class for expected, controllable analysis-service failures."""


class UnknownScenarioError(AnalysisServiceError):
    """The requested scenario id is not registered in the simulation registry."""


def _make_run_id(request: AnalysisRunRequest) -> str:
    scenario = request.scenario or "normal"
    return f"run-{request.seed}-{request.days:g}-{request.reference_seed}-{scenario}"


def _to_incident_out(incident: Incident, ai_result: AnalysisResult) -> AnalysisIncidentOut:
    evidence = incident.evidence
    return AnalysisIncidentOut(
        incident=DeterministicIncidentOut(
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
            classification_reason=incident.classification_reason,
            explanation=incident.explanation,
        ),
        evidence=IncidentEvidenceOut(
            contributing_signals=[
                ContributingSignalOut(
                    metric=signal.metric,
                    direction=signal.direction,
                    anomaly_count=signal.anomaly_count,
                    mean_z=signal.mean_z,
                    mean_abs_z=signal.mean_abs_z,
                )
                for signal in incident.contributing_signals
            ],
            signal_types=list(evidence.signal_types),
            evidence_score=evidence.evidence_score,
            temporal_coherence=evidence.temporal_coherence,
            spatial_coherence=evidence.spatial_coherence,
            signal_diversity=evidence.signal_diversity,
            persistence_minutes=evidence.persistence_minutes,
            sensor_anomaly_count=evidence.sensor_anomaly_count,
            citizen_report_count=evidence.citizen_report_count,
        ),
        ai=AIInfoOut(
            source=ai_result.source,
            ai_available=ai_result.ai_available,
            fallback_reason=ai_result.fallback_reason,
        ),
        analysis=ai_result.analysis,
    )


class AnalysisService:
    """Executes the deterministic analysis pipeline for one request."""

    def __init__(self, orchestrator: AIOrchestrator | None = None) -> None:
        self._orchestrator = orchestrator if orchestrator is not None else AIOrchestrator()

    def run_analysis(self, request: AnalysisRunRequest) -> AnalysisRunResponse:
        """Run one deterministic analysis and return the compact API response."""
        scenario_ids = ()
        if request.scenario is not None:
            if request.scenario not in SCENARIOS:
                raise UnknownScenarioError(
                    f"Unknown scenario {request.scenario!r}; registered: "
                    + ", ".join(sorted(SCENARIOS))
                )
            scenario_ids = (request.scenario,)

        duration_hours = request.days * 24.0
        target = run_simulation(
            build_config(
                seed=request.seed,
                duration_hours=duration_hours,
                scenario_ids=scenario_ids,
            )
        )
        reference = run_simulation(
            build_config(
                seed=request.reference_seed,
                duration_hours=REFERENCE_WINDOW_DAYS * 24.0,
            )
        )

        correlation = correlate_evidence(
            detect_anomalies(reference.measurements, target.measurements),
            target.reports,
        )
        assessments = assess_groups(correlation.groups, target.zones)

        incidents: list[AnalysisIncidentOut] = []
        ai_source_count = 0
        fallback_count = 0
        for assessment in assessments:
            if not assessment.qualified or assessment.incident is None:
                continue
            incident = assessment.incident
            ai_result = self._orchestrator.analyze(build_ai_context(incident))
            incidents.append(_to_incident_out(incident, ai_result))
            if ai_result.source is AnalysisSource.AI:
                ai_source_count += 1
            else:
                fallback_count += 1

        return AnalysisRunResponse(
            run=AnalysisRunMetadata(
                run_id=_make_run_id(request),
                seed=request.seed,
                days=request.days,
                scenario=request.scenario,
                reference_seed=request.reference_seed,
                ran_at=datetime.now(timezone.utc),
            ),
            incidents=incidents,
            summary=AnalysisRunSummary(
                incidents=len(incidents),
                ai_source_count=ai_source_count,
                fallback_count=fallback_count,
                zones=len(target.zones),
                window_hours=round(duration_hours, 2),
            ),
        )