# Analysis API

> Phase 3-C1 — exposes the deterministic intelligence pipeline and the Phase
> 3-B3 AI orchestration through a single versioned FastAPI endpoint. The API is
> an adapter: it contains no anomaly/correlation/risk formulas and no AI
> fallback logic — it reuses the locked intelligence modules as-is.

## Endpoint

`POST /api/v1/analysis/run`

Runs one deterministic analysis over simulated water-network data.

### Request

```jsonc
{
  "seed": 42,                 // int, 0..100000 (simulation seed)
  "days": 1,                  // float, >0..30 (target window in days)
  "scenario": "ZONE_B_SUPPLY_INCIDENT",  // optional, registered scenario id
  "reference_seed": 99        // int, 0..100000 (reference/baseline window seed)
}
```

- `scenario` optional. `null`/omitted ⇒ normal network run (no injected
  incident).
- Scenario ids come from the simulation registry (`app/simulation/scenarios.py`,
  currently just `ZONE_B_SUPPLY_INCIDENT`); unknown ids return HTTP 422.
- The reference window is a fixed 7-day baseline
  (`REFERENCE_WINDOW_DAYS` in `app/services/analysis.py`), matching the
  convention used across the intelligence test suite.

### Response

```jsonc
{
  "run": {
    "run_id": "run-42-1-99-ZONE_B_SUPPLY_INCIDENT",
    "seed": 42,
    "days": 1,
    "scenario": "ZONE_B_SUPPLY_INCIDENT",
    "reference_seed": 99,
    "data_source": "deterministic-simulation",
    "ran_at": "2026-08-28T...Z"
  },
  "incidents": [
    {
      "incident": {
        // deterministic, authoritative fields
        "incident_id": "INC-B-20260101T060000Z",
        "zone_id": "B",
        "incident_type": "WATER_LOSS",
        "status": "DETECTED",
        "severity": "CRITICAL",
        "risk_score": 91.52,
        "confidence": 0.9918,
        "start_time": "...",
        "last_updated": "...",
        "estimated_affected_population": 32000,
        "classification_reason": "...",
        "explanation": "..."
      },
      "evidence": {
        "contributing_signals": [ { "metric": "pressure", "direction": "below", ... } ],
        "signal_types": ["flow", "pressure", "quality", "consumption"],
        "evidence_score": 0.985,
        "persistence_minutes": 345,
        "sensor_anomaly_count": 89,
        "citizen_report_count": 12,
        "...": "..."
      },
      "ai": {
        "source": "AI" | "FALLBACK",
        "ai_available": true | false,
        "fallback_reason": "PROVIDER_UNAVAILABLE" | ...
      },
      "analysis": { /* AIIncidentAnalysis (structured, advisory) */ }
    }
  ],
  "summary": {
    "incidents": 1,
    "ai_source_count": 0,
    "fallback_count": 1,
    "zones": 4,
    "window_hours": 24.0
  }
}
```

## Behavior

- **Normal run** (`seed=42`, no scenario): HTTP 200, empty `incidents`, counts
  of zero. No incident is manufactured.
- **Golden Zone B** (`seed=42`, `days=1`,
  `scenario=ZONE_B_SUPPLY_INCIDENT`): one incident — `WATER_LOSS`/`CRITICAL`,
  risk ≈ 91.52, confidence ≈ 0.9918, evidence ≈ 0.985, 4 signal types, 89
  anomalies, 12 citizen reports, population 32 000.
- **AI success**: `ai.source = "AI"`, `ai_available = true`.
- **AI fallback**: if the AI provider fails (e.g. missing `GEMINI_API_KEY`), the
  deterministic incident stays intact and `ai.source = "FALLBACK"` with a safe
  categorized `fallback_reason`. HTTP status remains 200 — a degraded AI
  explanation is never an incident failure.
- No database persistence: each request is an independent in-memory analysis.

## Status codes

| code | meaning                                            |
| ---- | -------------------------------------------------- |
| 200  | successful run (including AI fallback)             |
| 422  | invalid request (bad seed/days, unknown scenario)  |
| 500  | unexpected application/programming failure         |

## Security

- The client only controls seed/days/scenario/reference_seed. No API keys,
  prompts, AI schemas, or infrastructure commands are accepted.
- Response never contains secrets, provider internals, or stack traces.
- No authentication is present yet (out of scope this phase).

## Examples

```bash
# Golden Zone B incident
curl -X POST http://localhost:8000/api/v1/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"seed":42,"days":1,"scenario":"ZONE_B_SUPPLY_INCIDENT"}'

# Normal network run
curl -X POST http://localhost:8000/api/v1/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"seed":42,"days":1}'
```

Interactive schema: http://localhost:8000/docs.

## Architecture

```
HTTP
 ↓
POST /api/v1/analysis/run        (app/api/routes/analysis.py)
 ↓
AnalysisService                  (app/services/analysis.py)
 ↓
simulation → anomaly detection → correlation → incident/risk
 ↓
build_ai_context → AIOrchestrator (injected via FastAPI dependency)
 ↓
AnalysisResult → API response    (app/schemas/analysis.py)
```

The data source is deterministic simulation — this is not a live water-system
feed.