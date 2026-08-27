"""Phase 4-B1 telemetry API routes.

FastAPI is an adapter here: the route stays thin, delegates to
``TelemetryService``, and contains no simulation or intelligence logic. The
endpoint is read-only simulation output — no anomaly/risk/AI computation, no
database, no persistence.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.telemetry import TelemetryRunRequest, TelemetryRunResponse
from app.services.analysis import UnknownScenarioError
from app.services.telemetry import TelemetryService

telemetry_router = APIRouter(tags=["telemetry"])


def get_telemetry_service() -> TelemetryService:
    """Default telemetry service dependency (stateless)."""
    return TelemetryService()


@telemetry_router.post(
    "/telemetry/run",
    response_model=TelemetryRunResponse,
    summary="Reproduce a deterministic telemetry run",
    description=(
        "Runs the deterministic simulator for the requested seed/days/scenario "
        "and returns the generated time-series measurements (timestamp, "
        "zone_id, metric, value, unit) together with zone metadata and scenario "
        "windows. This is a read-only simulation export: no anomaly detection, "
        "no risk scoring, no AI. Data source is deterministic simulation, not a "
        "live feed, and nothing is stored."
    ),
)
def run_telemetry(
    request: TelemetryRunRequest,
    service: TelemetryService = Depends(get_telemetry_service),
) -> TelemetryRunResponse:
    try:
        return service.get_telemetry(request)
    except UnknownScenarioError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc