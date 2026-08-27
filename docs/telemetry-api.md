# Telemetry API

> Phase 4-B1 — exposes the deterministic simulator's already-generated
> time-series measurements so a later frontend phase can render real telemetry
> charts. The endpoint is an adapter: it contains no anomaly/correlation/risk
> formulas and no AI — it calls the existing simulator and serializes its
> `SimulationResult.measurements` verbatim.

## Endpoint

`POST /api/v1/telemetry/run`

Reproduces one deterministic simulation and returns its measurements. POST is
used because scenario/run parameters are required to identify a particular
deterministic run (same convention as `/api/v1/analysis/run`).

### Request

```jsonc
{
  "seed": 42,       // int, 0..100000 (simulation seed)
  "days": 1,        // float, >0..30 (window in days, fractional allowed)
  "scenario": "ZONE_B_SUPPLY_INCIDENT"  // optional, registered scenario id
}
```

- `scenario` optional. `null`/omitted ⇒ normal network run (no injected
  incident). Scenario ids come from the same registry as `/analysis/run`
  (`app/simulation/scenarios.py`); unknown ids return HTTP 422.
- `reference_seed` is intentionally NOT accepted: it only controls the separate
  7-day reference window used for anomaly scoring and never changes the
  simulated measurements, so it has no effect on telemetry.

### Response

```jsonc
{
  "run": {
    "run_id": "telemetry-42-1-ZONE_B_SUPPLY_INCIDENT",
    "seed": 42,
    "days": 1,
    "scenario": "ZONE_B_SUPPLY_INCIDENT",
    "data_source": "deterministic-simulation",
    "window_hours": 24.0,
    "zone_count": 4,
    "measurement_count": 1536,
    "ran_at": "2026-08-28T...Z"
  },
  "zones": [
    { "zone_id": "A", "name": "Zone A", "district": "Central",
      "area_sq_km": 18.5, "estimated_population": 45000 }
    // ... B, C, D
  ],
  "measurements": [
    {
      "timestamp": "2026-01-01T00:00:00Z",
      "zone_id": "A",
      "metric": "flow",          // flow | pressure | quality | consumption
      "value": 3553.55,
      "unit": "m3/h"
    }
    // ...
  ],
  "scenarios": [
    {
      "scenario_id": "ZONE_B_SUPPLY_INCIDENT",
      "zone_id": "B",
      "window_start": "2026-01-01T06:00:00Z",
      "window_end": "2026-01-01T12:00:00Z",
      "description": "Supply disruption in Zone B: ..."
    }
  ]
}
```

Every field is an exact projection of a deterministic simulation model:

| response field | source (verbatim)                                |
| -------------- | ------------------------------------------------ |
| `zones[]`      | `Zone` (`app/simulation/models.py`)             |
| `measurements[]` | `Measurement` — timestamp, zone_id, metric, value, unit |
| `scenarios[]`  | `ScenarioOutcome` — which scenario ran, where, when |

Nothing is interpolated, derived, reconstructed, or hardcoded. `measurements`
are sorted by `(timestamp, zone_id, metric)` for convenient plotting; values
and units are untouched.

## Units and cadence

| metric        | unit  | meaning                                  |
| ------------- | ----- | ---------------------------------------- |
| `flow`        | m³/h  | inflow into the zone                     |
| `pressure`    | bar   | network pressure                         |
| `quality`     | mg/L  | free-chlorine residual (quality proxy)   |
| `consumption` | m³/h  | usable demand in the zone                |

Cadence is 15 minutes (the simulator's fixed `interval_minutes`), measured
from `2026-01-01T00:00:00Z`. Timestamps are timezone-aware UTC.

## Deterministic behavior

- Same `seed` (+ same `scenario`) ⇒ byte-identical measurements and `run_id`.
- Different `seed` ⇒ different stochastic values.
- A scenario perturbs **only** its target zone inside its window, applied
  *after* generation as a pure transformation. Zones A, C, D (and the target
  zone outside its window) are bit-identical to the corresponding normal run.
  This is enforced by tests.

### Golden Zone B scenario

`seed=42`, `days=1`, `scenario=ZONE_B_SUPPLY_INCIDENT`:

- 4 zones, 96 timestamps per zone, 1536 measurements.
- Incident window `2026-01-01T06:00:00Z` → `12:00Z` in Zone B.
- Verified live: Zone B pressure drops to ≈ 2.18 bar inside the window vs
  ≈ 4.03 bar outside; flow rises, consumption and quality fall (see
  `docs/simulation.md` for the exact scenario semantics).

## Consistency with `/api/v1/analysis/run`

`/analysis/run` builds its target simulation with
`build_config(seed=<seed>, duration_hours=<days>*24, scenario_ids=<scenario>)`
and runs anomaly detection against a *separate* 7-day reference window
(`reference_seed`). Telemetry uses the **same** `build_config` call for the
target window only:

```
analysis target simulation :  run_simulation(seed, days*24h, scenario)
telemetry  measurement set :  run_simulation(seed, days*24h, scenario)   ← identical
analysis reference window  :  run_simulation(reference_seed, 7*24h, no scenario)
```

Therefore `telemetry(seed, days, scenario)` is the exact measurement series
that `analysis(seed, days, scenario, any reference_seed)` was scored against.
The simulator is the sole source of measurements for both endpoints; there is
exactly one simulation code path.

## Response-size expectations

15-minute cadence × 4 zones × 4 metrics:

- measurements/day = 96 × 4 × 4 = **1 536** (~150–250 KB JSON)
- max window (30 days) = **46 080** measurements (~4–6 MB JSON)

No pagination is implemented: the current 30-day cap keeps the response finite
and this is a hackathon/local use case. Typical dashboard use is 1–7 days
(≈1.5k–10k rows). Documented scale; revisit pagination only if a longer window
becomes a real requirement.

## Behavior guarantees

- **No AI.** No Gemini, no orchestrator; the response contains no
  `ai`/`analysis` fields.
- **No intelligence.** No anomaly scores, risk, evidence, confidence, or
  classification — the endpoint goes simulation → serialize measurements only.
- **No persistence.** Each request is an independent in-memory deterministic
  run; nothing is stored.
- **No database** and **no simulation-API coupling**: the simulation package
  imports neither FastAPI nor Pydantic (enforced by a test).

## Status codes

| code | meaning                                   |
| ---- | ----------------------------------------- |
| 200  | successful telemetry run                  |
| 422  | invalid request (bad seed/days, unknown scenario) |
| 500  | unexpected application/programming failure |

## Security

- The client only controls `seed`/`days`/`scenario`. No API keys, prompts,
  filesystem paths, or provider/database credentials are accepted or returned.
- Response never contains stack traces or internal objects.
- Scenario validation reuses the existing `SCENARIOS` registry (no duplicate
  registry in the API layer).

## Intended frontend visualization use (next phase)

The future chart consumes the response directly:

```
telemetry
  ↓ filter zone            (measurements[].zone_id)
  ↓ filter metric          (measurements[].metric)
  ↓ plot timestamp/value   (measurements[].timestamp, measurements[].value)
```

with `zones[]` for labels/population and `scenarios[]` for the incident-window
overlay. No client-side data reconstruction is needed.

### Anomaly overlay (deferred, Phase 4-B1 does not implement it)

Associating anomaly markers with measurements is structurally unambiguous:
`AnomalyResult` carries the identical `(zone_id, metric, timestamp)` key and
scoring is a pure 1:1 map over measurements (using the 7-day reference
window). A future phase may overlay markers without changing the intelligence
model — but it must NOT be done client-side (AGENTS.md forbids client-side
intelligence) and must NOT be bolted onto this endpoint (it doesn't run the
reference window). Recommended path: emit per-measurement anomaly flags from
the existing analysis pipeline and export them from the analysis/telemetry
contract, rather than recomputing z-scores here.

## Architecture

```
HTTP
 ↓
POST /api/v1/telemetry/run      (app/api/routes/telemetry.py)
 ↓
TelemetryService                (app/services/telemetry.py)
 ↓
build_config → run_simulation   (app/simulation/* — reused verbatim)
 ↓
TelemetryRunResponse            (app/schemas/telemetry.py)
```