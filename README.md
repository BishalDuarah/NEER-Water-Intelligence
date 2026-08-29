# NEER — Water Intelligence & Response Platform

> **From fragmented water-network signals to explainable, prioritized incident intelligence.**

NEER is an AI-assisted water intelligence and decision-support platform designed to help **water-system operators** detect, correlate, investigate, and prioritize potential network incidents from multiple signals.

Instead of requiring operators to manually inspect individual sensor readings, NEER transforms telemetry into a structured incident workflow:

```text
Telemetry
   │
   ▼
Anomaly Detection
   │
   ▼
Signal Correlation
   │
   ▼
Incident Classification
   │
   ▼
Risk & Severity Assessment
   │
   ▼
AI-assisted Interpretation
   │
   ▼
Operator Investigation
   │
   ▼
Human Decision / Field Response



Then continue with these sections.

---

## The Problem

Water-system operators receive information from multiple sources—pressure, flow, consumption, water quality, and citizen reports.

The difficulty is not simply detecting an abnormal reading. The challenge is determining whether **multiple seemingly independent signals are related to the same underlying incident**.

A single pressure anomaly may be noise.

But:

```text
Pressure anomaly
       +
Flow anomaly
       +
Consumption anomaly
       +
Water-quality anomaly
       +
Citizen reports
       ↓
Correlated evidence
       ↓
Potential incident

NEER is designed to turn these fragmented signals into a prioritized, evidence-backed incident for operator investigation.


How NEER Works
Water Telemetry
      ↓
Time-of-Day Baseline
      ↓
Anomaly Detection
      ↓
Multi-Signal Correlation
      ↓
Incident Classification
      ↓
Risk & Severity Assessment
      ↓
AI Interpretation
      ↓
Operator Investigation
      ↓
Human / Field Response
1. Telemetry

The prototype uses a deterministic water-network simulator representing four zones:

Zone A, B, C and D

It generates:

Flow
Pressure
Water quality
Consumption
Citizen reports

Telemetry is generated at a 15-minute cadence.

2. Anomaly Detection

NEER compares measurements against time-of-day reference baselines and identifies statistically abnormal observations.

3. Signal Correlation

Rather than creating an alert for every abnormal measurement, NEER groups related anomalies using:

Zone
Temporal proximity
Signal diversity
Persistence
Evidence coherence
Citizen reports
4. Incident & Risk Assessment

Strong evidence groups become structured incidents containing:

Incident type
Risk score
Severity
Confidence
Contributing signals
Persistence
Estimated affected population
5. AI-Assisted Investigation

Gemini provides an interpretation of the already-computed incident evidence.

It can provide:

Possible causes
Evidence interpretation
Suggested investigation steps
Advisory response options
Uncertainty

The deterministic engine remains authoritative.

Operator Workflow

NEER is not a replacement for field personnel.

The operator is the person responsible for monitoring and managing the water network from the operational/control side, prioritizing incidents and deciding what requires investigation or field response.

Sensors / Reports
       ↓
      NEER
       ↓
Detect + Correlate
       ↓
Assess + Prioritize
       ↓
Operator Dashboard
       ↓
Investigation
       ↓
Field / Operational Response

NEER answers:

"Which zone needs attention first, and what evidence supports that decision?"

Physical inspection, maintenance, valve operations, emergency dispatch, and repairs remain human responsibilities.

AI Safety & Human-in-the-Loop

NEER separates deterministic assessment from AI interpretation.

Deterministic system owns
Measurements
Anomaly detection
Evidence scores
Incident classification
Risk
Severity
Confidence
Population estimates
AI provides
Interpretation
Possible causes
Investigation suggestions
Advisory recommendations
Uncertainty explanation

AI cannot execute infrastructure actions or override the deterministic incident assessment.

If Gemini is unavailable, NEER falls back to a deterministic analysis so the operator still receives incident intelligence.

Demonstration Scenario

The main demonstration models a potential water-loss incident in Zone B.

The simulator introduces a controlled incident affecting multiple telemetry signals during a defined time window.

NEER then:

Detects abnormal signals
        ↓
Correlates them
        ↓
Builds evidence
        ↓
Calculates risk
        ↓
Creates incident
        ↓
Provides AI/fallback interpretation
        ↓
Allows operator investigation

The dashboard allows the judge to move from:

Simulation → Incident Queue → Investigation → Telemetry

using the same backend-generated data.

Why a Simulator?

The prototype does not have access to live municipal infrastructure, deployed IoT sensors, or proprietary SCADA data.

Instead of using arbitrary mock values, NEER uses a deterministic simulator that provides reproducible telemetry and controlled incident scenarios.

This allows the entire intelligence pipeline to be tested consistently.

Importantly, the intelligence pipeline is separated from the telemetry source:

Prototype

Deterministic Simulator
        ↓
Telemetry API
        ↓
NEER Intelligence Pipeline


Production

IoT / SCADA / Municipal Data
        ↓
Telemetry Ingestion
        ↓
NEER Intelligence Pipeline

Therefore, the simulator is a prototype data source, not the intended production architecture.

Current Capabilities
Capability	Status
Deterministic water simulation	✅
Telemetry API	✅
Real telemetry visualization	✅
Anomaly detection	✅
Multi-signal correlation	✅
Citizen-report correlation	✅
Incident classification	✅
Risk & severity assessment	✅
Gemini AI interpretation	✅
Deterministic AI fallback	✅
Incident investigation view	✅
Real IoT ingestion	🔜
Municipal data integration	🔜
Persistent incident management	🔜
Authentication / RBAC	🔜
Multi-tenant deployment	🔜
Real-time streaming	🔜
SCADA integration	🔜
Architecture
┌──────────────────────────────────────────────┐
│                 FRONTEND                     │
│                                              │
│ Operations │ Water Network │ Incidents      │
│                                              │
│ Telemetry │ Investigation │ AI Analysis      │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│                 FASTAPI                     │
│                                              │
│ /analysis/run       /telemetry/run           │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│          DETERMINISTIC INTELLIGENCE         │
│                                              │
│ Simulation                                  │
│     ↓                                        │
│ Baseline → Anomaly Detection                │
│     ↓                                        │
│ Signal Correlation                          │
│     ↓                                        │
│ Incident + Risk Assessment                  │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│                  AI LAYER                   │
│                                              │
│ Structured Context → Gemini                 │
│                       ↓                     │
│                  Validation                 │
│                       ↓                     │
│             Deterministic Fallback           │
└──────────────────────────────────────────────┘
Technology Stack

Backend

Python
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Google Gemini

Frontend

React
TypeScript
Vite
Tailwind CSS
Vitest
React Testing Library
SVG-based telemetry visualization

Engineering

Deterministic simulation
Statistical anomaly detection
Evidence correlation
Risk assessment
Structured AI output
Automated testing
Docker Compose
Running Locally
Backend
cd backend
python -m venv .venv

Windows PowerShell:

.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
Frontend
cd frontend
npm install
npm run dev

Open:

http://localhost:5173

Backend:

http://localhost:8000

Gemini is optional:

$env:GEMINI_API_KEY="your-key"

Without a Gemini key, NEER uses its deterministic fallback analysis.

Verification

The current prototype has been verified through automated tests and live integration tests.

Backend
267 passed
1 skipped
Frontend
94 passed
5 skipped

Additional verification covers:

API contracts
deterministic simulation
anomaly detection
correlation
incident assessment
AI provider failures
deterministic fallback
telemetry visualization
frontend integration
golden Zone B scenario
Production Roadmap

The prototype can be extended with:

Real IoT/SCADA ingestion
Municipal water datasets
Persistent incident management
Authentication and RBAC
Multi-tenant organizations
Real-time WebSockets/SSE
GIS/network topology
Field-team coordination
Historical analytics
Operational audit logs
Documentation

Detailed technical documentation is available in docs/.

Key documents:

Simulation
Anomaly Detection
Correlation
Incident & Risk Design
AI Context Contract
Analysis API
Telemetry API
