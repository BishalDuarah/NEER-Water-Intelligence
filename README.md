# NEER — Water Intelligence & Response Platform

Decision-support platform that turns simulated water-system data into early
incident detection, risk intelligence, and response recommendations.
This repository is in **Phase 4-A1 (Frontend Operations Dashboard)** — the
Phase 0 foundation (skeleton, database connection, health endpoint,
frontend↔backend comms), the Phase 1 deterministic water-network data
generator, a signal-level intelligence module that scores each measurement
against a time-of-day baseline (Phase 2A), a correlation engine that groups
same-zone anomalies + citizen reports into scored evidence groups (Phase 2B),
and a deterministic incident + risk engine that turns strong evidence into
actionable incidents with classification, severity, and confidence (Phase
2C-B). Phase 3-A fixed the AI contract; Phase 3-B1 implemented its data layer —
the `IncidentAIContext`, `AIIncidentAnalysis` schema, and `AIProvider`
interface; Phase 3-B2 adds the concrete Gemini provider behind that interface
(`gemini_provider.py`, `google-genai` SDK, structured output re-validated
locally, opt-in live test); Phase 3-B3 adds the orchestrator that gates AI
consumption and fails safely onto a deterministic analysis
(`ai_orchestrator.py`: `AIOrchestrator`, deterministic `build_fallback_analysis`);
Phase 3-C1 exposes all of that through a small FastAPI analysis endpoint
(`POST /api/v1/analysis/run` — see [`docs/analysis-api.md`](docs/analysis-api.md));
Phase 4-A1 builds the operations dashboard that closely reproduces the Aqua
Sentinel/NEER prototype's information architecture and dark design system,
consuming the 3-C1 API as the single source of truth (no mock data, no
client-side intelligence).
See
[`docs/simulation.md`](docs/simulation.md),
[`docs/anomaly_detection.md`](docs/anomaly_detection.md),
[`docs/correlation.md`](docs/correlation.md),
[`docs/incident-risk-design.md`](docs/incident-risk-design.md) and
[`docs/ai-context-contract.md`](docs/ai-context-contract.md).

See `AGENTS.md` for architecture rules and the hard constraints that govern
this project.

## Architecture (Phase 4-A1)

- **Backend**: Python + FastAPI, SQLAlchemy, Pydantic, PostgreSQL
- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Database**: PostgreSQL (via Docker Compose for local dev)
- **Simulation**: `backend/app/simulation/` — deterministic, DB/FastAPI-independent
  data generator (zones, normal measurements, incident scenarios, citizen reports)
- **Intelligence**: `backend/app/intelligence/` — time-of-day baselines +
  bidirectional z-score anomaly detection (Phase 2A), gap-based correlation of
  anomalies + citizen reports into scored evidence groups (Phase 2B), and a
deterministic incident + risk engine (Phase 2C-B) that qualifies evidence
   groups and produces `IncidentAssessment` objects (classification, risk,
   severity, confidence). Phase 3-B1 adds the AI boundary: `IncidentAIContext`
   (+ `build_ai_context` / `serialize_context`), the `AIIncidentAnalysis`
   output schema, and the `AIProvider` interface. Phase 3-B2 implements the
   concrete Gemini provider (`gemini_provider.py`) behind that interface —
   `google-genai` SDK, single structured-output call, deterministic
   `SYSTEM_INSTRUCTIONS`, local `AIIncidentAnalysis` re-validation, typed
   `AIProviderError` mapping, and `GEMINI_API_KEY` from the environment.
   Phase 3-B3 adds the orchestration gate (`ai_orchestrator.py`): one provider
   attempt per incident via `AIOrchestrator.analyze`, and any `AIProviderError`
   falls back to the deterministic `build_fallback_analysis` (safe categorized
   `fallback_reason`, incident preserved, no retries). Phase 3-C1 adds the
   analysis API: `AnalysisService` (`app/services/analysis.py`) runs the
   pipeline for `POST /api/v1/analysis/run`, mapping results onto the compact
   `AnalysisRunResponse` schema (`app/schemas/analysis.py`) via a route that
   receives its `AIOrchestrator` through dependency injection — so AI is
   optional/enhancement, deterministic fallback stays available, and there is
   still no persistence or frontend AI UI yet.

```
backend/   FastAPI app, config, db session, /health, tests

app/simulation/    data generator (Phase 1)
           app/intelligence/  baselines + anomaly detection (2A), correlation (2B),
                               incident + risk assessment (2C-B),
                               AI context/output models + provider interface (3-B1),
                               Gemini provider integration (3-B2),
                               orchestration + deterministic fallback (3-B3)
           app/services/      application service layer (3-C1 analysis service)
           app/schemas/       Pydantic API boundary schemas (health, analysis)
           app/api/routes/    FastAPI adapters (health, analysis /run)
frontend/  React app: analysis API client, operations dashboard
           (Operations / Water Network / Incidents tabs), dark design system,
           vitest + testing-library tests
docs/      simulation.md, anomaly_detection.md, correlation.md, incident-risk-design.md,
           ai-context-contract.md, analysis-api.md
docker-compose.yml  PostgreSQL service
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for local PostgreSQL)
- (optional) a `GEMINI_API_KEY` environment variable to run the provider live

## Setup

### 1. Start PostgreSQL

```bash
docker compose up -d postgres
```

### 2. Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -e ".[dev]"
copy .env.example .env              # adjust DATABASE_URL if needed
uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
pytest
```

Optionally run against the live Gemini API (requires `GEMINI_API_KEY`):

```bash
$env:NEER_RUN_LIVE_GEMINI_TEST="1"; $env:GEMINI_API_KEY="your-key"; pytest
```

The provider reads `GEMINI_API_KEY` from the environment; it is never logged,
committed, or shown in errors.

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

The app is served at http://localhost:5173 and calls the backend
`POST /api/v1/analysis/run` endpoint (see
[`docs/analysis-api.md`](docs/analysis-api.md)). The Operations dashboard
("Network Command View") includes the Incident Simulation Engine (scenario
toggle + run), the 5-stat network summary, Zone Health Overview, Active
Incidents queue, and Citizen Reports. `VITE_API_BASE_URL` defaults to
`http://localhost:8000`; the backend CORS allows `http://localhost:5173`.

Run the frontend tests:

```bash
npm test
```

The two live-integration tests are skipped unless `NEER_LIVE_INTEGRATION=1`
and a backend is running on port 8000.

### 4. Run the simulator (Phase 1)

```bash
cd backend
python -m app.simulation --seed 42 --days 1                                   # normal network
python -m app.simulation --seed 42 --days 1 --scenario ZONE_B_SUPPLY_INCIDENT  # Zone B incident
```

### 5. Run anomaly detection (Phase 2A)

```python
from app.simulation import build_config, run_simulation
from app.intelligence import detect_anomalies

reference = run_simulation(build_config(seed=99, duration_hours=7 * 24.0)).measurements
target = run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))
findings = detect_anomalies(reference, target.measurements)
anomalies = [f for f in findings if f.is_anomalous]
```

### 6. Correlation (Phase 2B)

```python
from app.simulation import build_config, run_simulation
from app.intelligence import detect_anomalies, correlate_evidence

reference = run_simulation(build_config(seed=99, duration_hours=7 * 24.0)).measurements
target = run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))
findings = detect_anomalies(reference, target.measurements)
result = correlate_evidence(findings, target.reports)

for group in result.groups:
    print(group.group_id, group.evidence_score, group.summary)
```

### 7. Incident generation + risk assessment (Phase 2C-B)

```python
from app.simulation import build_config, run_simulation
from app.intelligence import assess_groups, correlate_evidence, detect_anomalies

reference = run_simulation(build_config(seed=99, duration_hours=7 * 24.0)).measurements
target = run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))
result = correlate_evidence(detect_anomalies(reference, target.measurements), target.reports)

for assessment in assess_groups(result.groups, target.zones):
    if not assessment.qualified:
        continue
    incident = assessment.incident
    print(incident.incident_id, incident.incident_type.value, incident.severity.value,
          incident.risk_score, round(incident.confidence, 3))
```

Expected golden output: one qualified Zone B incident
(`WATER_LOSS` / `CRITICAL`, risk ≈ 91.5, confidence ≈ 0.99).

### 8. AI analysis (Phase 3-B2 — needs `GEMINI_API_KEY`)

```python
from app.simulation import build_config, run_simulation
from app.intelligence import (
    GeminiProvider, build_ai_context, assess_groups,
    correlate_evidence, detect_anomalies,
)

reference = run_simulation(build_config(seed=99, duration_hours=7 * 24.0)).measurements
target = run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))
incident = next(
    a.incident for a in assess_groups(
        correlate_evidence(detect_anomalies(reference, target.measurements), target.reports),
        target.zones,
    )
    if a.qualified and a.incident is not None
)

provider = GeminiProvider()                      # reads GEMINI_API_KEY
analysis = provider.generate_analysis(build_ai_context(incident))
print(analysis.incident_id, analysis.summary[:80])
```

### 9. AI orchestration with deterministic fallback (Phase 3-B3)

`AIOrchestrator` is the single gate for AI consumption: one provider attempt
per incident; on any provider failure NEER still returns a deterministic
fallback analysis built from the context. It also works without
`GEMINI_API_KEY`:

```python
from app.simulation import build_config, run_simulation
from app.intelligence import (
    AIOrchestrator, build_ai_context, assess_groups,
    correlate_evidence, detect_anomalies,
)

reference = run_simulation(build_config(seed=99, duration_hours=7 * 24.0)).measurements
target = run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))
incident = next(
    a.incident for a in assess_groups(
        correlate_evidence(detect_anomalies(reference, target.measurements), target.reports),
        target.zones,
    )
    if a.qualified and a.incident is not None
)

result = AIOrchestrator().analyze(build_ai_context(incident))
print(result.source.value)      # "AI" (Gemini) or "FALLBACK" (deterministic)
print(result.analysis.summary)  # always a valid AIIncidentAnalysis
```

### 10. Analysis API (Phase 3-C1)

Start the backend (see Setup) and call `POST /api/v1/analysis/run`:

```bash
# Golden Zone B incident
curl -X POST http://localhost:8000/api/v1/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"seed":42,"days":1,"scenario":"ZONE_B_SUPPLY_INCIDENT"}'

# Normal network run (no scenario)
curl -X POST http://localhost:8000/api/v1/analysis/run \
  -H "Content-Type: application/json" \
  -d '{"seed":42,"days":1}'
```

The API runs the deterministic simulation + intelligence pipeline and attaches
an AI explanation to each qualified incident. AI is optional/enhancement: when
`GEMINI_API_KEY` is absent the endpoint still returns HTTP 200 with
`ai.source="FALLBACK"` and the deterministic incident/risk/severity/evidence
intact. See [`docs/analysis-api.md`](docs/analysis-api.md) for the full contract.
The data source is deterministic simulation, not a live water-system feed.

## Verify

- `GET http://localhost:8000/health` → `{"status":"ok"}`
- `GET http://localhost:8000/api/v1/health` → structured status (DB `ok` when
  PostgreSQL is reachable)
- `POST http://localhost:8000/api/v1/analysis/run` → analysis JSON (golden and
  normal runs above)
- Frontend the "Operations dashboard" ("Network Command View"): pick a scenario
  ("Normal operation" or `ZONE_B_SUPPLY_INCIDENT`), press "Simulate Water
  Incident", and confirm the deterministic incident rows, network status pill,
  zone health, incident queue, and citizen reports render from the API response.
- `python -m app.simulation` produces reproducible measurement output.

## What is NOT implemented yet

Operator workflows / incident lifecycle management (assign → resolve) and
PostgreSQL persistence for intelligence findings (each API run is an
independent in-memory analysis) are designed but not implemented. Raw telemetry
time-series (per-zone charts, real sensor streams) is also not implemented —
the Water Network tab and the telemetry panels are honest placeholders until a
telemetry API phase exists.
Incident generation, classification, risk scoring, severity, and confidence are
implemented deterministically in Phase 2C-B (`backend/app/intelligence/incident.py`,
tested in `backend/tests/test_incident_risk.py`); the AI context/output schemas
and provider interface are implemented in Phase 3-B1 (`ai_context.py`,
`ai_analysis.py`, `ai_provider.py`, tested in
`backend/tests/test_ai_context_contract.py`); the concrete Gemini provider in
Phase 3-B2 (`gemini_provider.py`, network-free fake-client tests in
`backend/tests/test_gemini_provider.py` plus an opt-in live Gemini test);
the orchestrator + deterministic fallback in Phase 3-B3 (`ai_orchestrator.py`,
tested in `backend/tests/test_ai_orchestrator.py`); and the analysis API in
Phase 3-C1 (`app/services/analysis.py`, `app/api/routes/analysis.py`,
`app/schemas/analysis.py`, tested in `backend/tests/test_analysis_api.py` and
`backend/tests/test_analysis_service.py`). Full regression:
**235 passed, 1 skipped**.
