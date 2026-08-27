# NEER — Water Intelligence & Response Platform

Decision-support platform that turns simulated water-system data into early
incident detection, risk intelligence, and response recommendations.
This repository is in **Phase 0 (Foundation)** — only the skeleton, database
connection, health endpoint, and basic frontend↔backend communication exist.

See `AGENTS.md` for architecture rules and the hard constraints that govern
this project.

## Architecture (Phase 0)

- **Backend**: Python + FastAPI, SQLAlchemy, Pydantic, PostgreSQL
- **Frontend**: React + Vite + TypeScript + Tailwind CSS
- **Database**: PostgreSQL (via Docker Compose for local dev)

```
backend/   FastAPI app, config, db session, /health, tests
frontend/  React app, API client, status view
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

## Verify

- `GET http://localhost:8000/health` → `{"status":"ok"}`
- `GET http://localhost:8000/api/v1/health` → structured status (DB `ok` when
  PostgreSQL is reachable)
- Frontend status view shows backend health, including DB connectivity.

## What is NOT implemented yet

Anomaly detection, signal correlation, risk scoring, incident management, the
AI/LLM layer, and the full dashboard are intentionally out of scope for Phase 0.
