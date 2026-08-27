"""The four MVP zones of the simulated water network.

Stable definitions with simple, extensible geographic metadata. The geographic
model is intentionally shallow (district + area) so it can grow without
rippling into the simulation math.
"""

from __future__ import annotations

from app.simulation.models import Zone

ZONES: list[Zone] = [
    Zone(zone_id="A", name="Zone A", district="Central", area_sq_km=18.5, estimated_population=45_000),
    Zone(zone_id="B", name="Zone B", district="Riverside", area_sq_km=12.0, estimated_population=32_000),
    Zone(zone_id="C", name="Zone C", district="North Industrial", area_sq_km=22.3, estimated_population=18_000),
    Zone(zone_id="D", name="Zone D", district="East Suburbs", area_sq_km=30.1, estimated_population=52_000),
]

ZONE_IDS: tuple[str, ...] = tuple(z.zone_id for z in ZONES)