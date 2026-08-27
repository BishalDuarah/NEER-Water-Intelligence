# Water Network Simulation (Phase 1)

## Purpose

Phase 1 produces the realistic, reproducible water-network **data layer** that
later phases consume. It is purely a data generator — anomaly detection, signal
correlation, risk scoring, incident classification, and the AI layer are out of
scope and not implemented here.

The simulator models four supply zones, generates timestamped sensor
measurements with controlled natural variation, and can overlay declarative
incident scenarios (e.g. a supply disruption in Zone B) that perturb
measurements and spawn citizen reports. With a fixed seed, the output is
byte-for-byte reproducible.

## Data structures

All structures are plain frozen dataclasses in `app/simulation/models.py`,
independent of PostgreSQL, FastAPI, and any AI/numerical stack. Adapters can
map them to Pydantic schemas / SQLAlchemy models later without touching the
simulation.

- `Zone` — `zone_id`, `name`, `district`, `area_sq_km`, `estimated_population`
- `Measurement` — `timestamp`, `zone_id`, `metric`, `value`, `unit`
- `CitizenReport` — `report_id`, `zone_id`, `timestamp`, `category`,
  `description`, `severity`, `status`
- `ScenarioOutcome` — which scenario ran, where, and when
- `SimulationResult` — `config`, `zones`, `measurements`, `reports`, `scenarios`

### Units (explicit, part of every `MetricProfile`)

| metric         | meaning                              | unit     |
| -------------- | ------------------------------------ | -------- |
| `flow`         | inflow into the zone                 | m³/h     |
| `pressure`     | network pressure                     | bar      |
| `quality`      | free-chlorine residual (quality proxy)| mg/L    |
| `consumption`  | usable demand in the zone            | m³/h     |

## Zones

| id | name          | district           | population |
| -- | ------------- | ------------------ | ---------- |
| A  | Zone A        | Central            | 45,000     |
| B  | Zone B        | Riverside          | 32,000     |
| C  | Zone C        | North Industrial   | 18,000     |
| D  | Zone D        | East Suburbs       | 52,000     |

## Normal behavior

Baseline values, acceptable ranges, and noise spread live per zone in
`SimulationConfig.profiles` (`app/simulation/config.py`):

- `flow` / `consumption`: baseline ∝ zone size, scaled by a smooth diurnal
  demand factor (`diurnal_factor`, night trough + lunch/evening peaks), plus
  Gaussian noise (±3% σ of baseline). Values are clamped to
  `[0.5×baseline, 1.6×baseline]`.
- `pressure`: base ~4.0–4.4 bar, edges slightly *down* as demand rises, ±0.06 bar
  noise, clamped to `[2.0, 6.0]` bar.
- `quality`: ~0.48–0.50 mg/L chlorine ±0.02, clamped to `[0.10, 1.20]` mg/L.

Measurements are spaced by `interval_minutes` (default 15 min) across
`duration_hours` (default 24 h). Each zone gets an independent RNG derived from
`seed` (`random.Random(f"{seed}:zone:{id}")`), so runs are deterministic but
not identical across zones.

## Scenarios

Scenarios are declarative `IncidentSpec` objects registered in `SCENARIOS`
(`app/simulation/scenarios.py`). Each specifies a target zone, a window
(start offset + duration from simulation start), per-metric multipliers
(ramped in over `incident_ramp_minutes` to avoid a hard step), and extra noise.

### `ZONE_B_SUPPLY_INCIDENT`

Zone B, 06:00–12:00 UTC by default. Applied to existing normal measurements:

- `pressure` × 0.50 — pressure drops to ~2.2 bar inside the window
- `flow` × 1.25 — inflow rises (lost water)
- `consumption` × 0.60 — usable demand falls (customers lose supply)
- `quality` × 0.85 — slight quality degradation
- citizen reports spike: `citizen_reports_per_scenario` (default 12)
  `low_pressure` (moderate) / `supply_disruption` (high) reports in Zone B

A scenario only rewrites measurements for its own zone. Zones A, C, D remain
bit-identical whether or not the scenario runs — this is enforced by a test.

## How to run

From `backend/`:

```bash
# normal network, 24 h at 15 min, seed 42
python -m app.simulation --seed 42 --days 1

# Zone B incident overlay
python -m app.simulation --seed 42 --days 1 --scenario ZONE_B_SUPPLY_INCIDENT

# custom window / cadence / reports
python -m app.simulation --seed 7 --days 2 --interval-minutes 5 --report-count 20
```

CLI flags: `--seed`, `--days`, `--interval-minutes`, `--scenario` (repeatable),
`--start-time` (ISO-8601 UTC), `--report-count`.

Python API:

```python
from app.simulation import build_config, run_simulation

result = run_simulation(build_config(scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))
result.measurements  # list[Measurement]
result.reports       # list[CitizenReport]
```

Run tests (Phase 0 + Phase 1):

```bash
python -m pytest
```

## Golden Zone B scenario — reproduction

```bash
python -m app.simulation --seed 42 --days 1 --scenario ZONE_B_SUPPLY_INCIDENT
```

Fixed knobs: seed 42, window `2026-01-01T00:00:00Z` → `2026-01-02T00:00:00Z`,
15 min cadence, incident 06:00–12:00 UTC in Zone B, 12 citizen reports. Zone B
means inside the incident window: pressure ≈ 2.18 bar (≈ 4.03 outside),
flow ≈ 3452 m³/h (≈ 2811 outside), consumption ≈ 1533 m³/h (≈ 2527 outside),
quality ≈ 0.42 mg/L (≈ 0.50 outside).