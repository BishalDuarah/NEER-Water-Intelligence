"""Phase 4-B1 application service: read-only telemetry retrieval.

``TelemetryService`` is the adapter that reproduces the deterministic simulator
run requested by a client (seed/days/scenario) and returns its measurements.
It performs NO intelligence work: no anomaly detection, no correlation, no risk
scoring, no classification, no AI. Its only job is:

    simulation -> serialize measurements

It reuses ``run_simulation`` / ``build_config`` verbatim (the simulator remains
the sole source of measurements) and the shared ``UnknownScenarioError`` from
the analysis service so scenario validation follows the exact same contract as
``/analysis/run`` and is rejected the same way (HTTP 422).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.telemetry import (
    TelemetryMeasurement,
    TelemetryRunMetadata,
    TelemetryRunRequest,
    TelemetryRunResponse,
    TelemetryScenario,
    TelemetryZone,
)
from app.services.analysis import UnknownScenarioError
from app.simulation import SCENARIOS, build_config, run_simulation


def _make_run_id(request: TelemetryRunRequest) -> str:
    scenario = request.scenario or "normal"
    return f"telemetry-{request.seed}-{request.days:g}-{scenario}"


class TelemetryService:
    """Reproduces one deterministic simulation and serializes its measurements."""

    def get_telemetry(self, request: TelemetryRunRequest) -> TelemetryRunResponse:
        scenario_ids: tuple[str, ...] = ()
        if request.scenario is not None:
            if request.scenario not in SCENARIOS:
                raise UnknownScenarioError(
                    f"Unknown scenario {request.scenario!r}; registered: "
                    + ", ".join(sorted(SCENARIOS))
                )
            scenario_ids = (request.scenario,)

        duration_hours = request.days * 24.0
        result = run_simulation(
            build_config(
                seed=request.seed,
                duration_hours=duration_hours,
                scenario_ids=scenario_ids,
            )
        )

        measurements = sorted(
            result.measurements, key=lambda m: (m.timestamp, m.zone_id, m.metric)
        )

        return TelemetryRunResponse(
            run=TelemetryRunMetadata(
                run_id=_make_run_id(request),
                seed=request.seed,
                days=request.days,
                scenario=request.scenario,
                window_hours=round(duration_hours, 2),
                zone_count=len(result.zones),
                measurement_count=len(measurements),
                ran_at=datetime.now(timezone.utc),
            ),
            zones=[
                TelemetryZone(
                    zone_id=zone.zone_id,
                    name=zone.name,
                    district=zone.district,
                    area_sq_km=zone.area_sq_km,
                    estimated_population=zone.estimated_population,
                )
                for zone in result.zones
            ],
            measurements=[
                TelemetryMeasurement(
                    timestamp=m.timestamp,
                    zone_id=m.zone_id,
                    metric=m.metric,
                    value=m.value,
                    unit=m.unit,
                )
                for m in measurements
            ],
            scenarios=[
                TelemetryScenario(
                    scenario_id=s.scenario_id,
                    zone_id=s.zone_id,
                    window_start=s.window_start,
                    window_end=s.window_end,
                    description=s.description,
                )
                for s in result.scenarios
            ],
        )