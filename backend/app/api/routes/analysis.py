"""Analysis API routes (Phase 3-C1).

FastAPI is an adapter here: routes stay thin, delegate to ``AnalysisService``,
and never touch simulation/intelligence internals or providers directly. The
``AIOrchestrator`` is provided through FastAPI dependency injection so tests can
inject a fake/stub orchestrator and never depend on live Gemini.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.intelligence import AIOrchestrator
from app.schemas.analysis import AnalysisRunRequest, AnalysisRunResponse
from app.services.analysis import AnalysisService, UnknownScenarioError

analysis_router = APIRouter(tags=["analysis"])


def get_orchestrator() -> AIOrchestrator:
    """Default orchestrator dependency (lazy; provider built on first use)."""
    return AIOrchestrator()


def get_analysis_service(
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
) -> AnalysisService:
    """Build the analysis service for one request with its orchestrator."""
    return AnalysisService(orchestrator)


@analysis_router.post(
    "/analysis/run",
    response_model=AnalysisRunResponse,
    summary="Run a deterministic analysis",
    description=(
        "Runs the deterministic simulation + intelligence pipeline for the "
        "requested seed/days/scenario and attaches an AI explanation to each "
        "qualified incident. The AI layer is optional: provider failures "
        "degrade to the deterministic fallback analysis, never to an HTTP "
        "error. Data source is deterministic simulation, not a live feed."
    ),
)
def run_analysis(
    request: AnalysisRunRequest,
    service: AnalysisService = Depends(get_analysis_service),
) -> AnalysisRunResponse:
    try:
        return service.run_analysis(request)
    except UnknownScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc