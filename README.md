# NEER — Water Intelligence & Response Platform

Decision-support platform that turns simulated water-system data into early
incident detection, risk intelligence, and response recommendations.
This repository is in **Phase 2A (Baseline + Anomaly Detection)** — the Phase 0
foundation (skeleton, database connection, health endpoint, frontend↔backend
comms), the Phase 1 deterministic water-network data generator, and a
signal-level intelligence module that scores each measurement against a
time-of-day baseline. See [`docs/simulation.md`](docs/simulation.md) and
[`docs/anomaly_detection.md`](docs/anomaly_detection.md).

See `AGENTS.md` for architecture rules and the hard constraints that govern
this project.

## Architecture (Phase 2A)

- **Backend**: Python + FastAPI, SQLAlchemy, Pydantic, PostgreSQL
- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Database**: PostgreSQL (via Docker Compose for local dev)
- **Simulation**: `backend/app/simulation/` — deterministic, DB/FastAPI-independent
  data generator (zones, normal measurements, incident scenarios, citizen reports)
- **Intelligence**: `backend/app/intelligence/` — time-of-day baselines +
  bidirectional z-score anomaly detection (signal-level, no incidents/risk yet)

```
backend/   FastAPI app, config, db session, /health, tests

           app/simulation/    data generator (Phase 1)
           app/intelligence/  baselines + anomaly detection (Phase 2A)
frontend/  React app, API client, status view
docs/      simulation.md, anomaly_detection.md
docker-compose.yml  PostgreSQL service
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (for local PostgreSQL)

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

### 3. Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

The app is served at http://localhost:5173 and calls the backend
`GET /api/v1/health` endpoint.

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

## Verify

- `GET http://localhost:8000/health` → `{"status":"ok"}`
- `GET http://localhost:8000/api/v1/health` → structured status (DB `ok` when
  PostgreSQL is reachable)
- Frontend status view shows backend health, including DB connectivity.
- `python -m app.simulation` produces reproducible measurement output.

## What is NOT implemented yet

Signal correlation, incident generation, incident classification, risk scoring,
incident management, the AI/LLM layer, FastAPI routes / PostgreSQL persistence
for intelligence findings, and the full dashboard are intentionally out of
scope for Phase 2A (next: correlation + incident generation).
