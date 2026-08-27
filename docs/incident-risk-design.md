# Incident & Risk Design

> Phase 2C-A established the DESIGN contract; the contract was implemented and
> calibrated in Phase 2C-B (`backend/app/intelligence/incident.py`).
> This document records both the contract and its implementation.

## Purpose

Phase 2C transforms **correlated evidence groups** (Phase 2B output) into
actionable **incident objects** with deterministic classification, risk
assessment, and severity. It occupies this pipeline position:

```
Simulation → Anomaly Detection → Correlated Evidence
    → Incident Assessment → Risk + Severity
        → AI-assisted explanation / recommendation (later)
```

Phase 2C is **fully deterministic**: classification, risk, severity, and
confidence are computed by documented statistical/rule logic in code. No LLM is
used anywhere in this phase. The LLM layer is a later phase and consumes these
results as structured context only.

Core vocabulary (kept distinct throughout):

| term                | meaning                                                          |
| ------------------- | ---------------------------------------------------------------- |
| Anomaly             | an unusual individual signal (Phase 2A)                          |
| Correlated Evidence | multiple observations spatially/temporally related, may represent a common event (Phase 2B) |
| Incident            | a correlated evidence group strong/actionable enough to represent a potential operational event (Phase 2C) |
| Risk                | estimated consequence/impact of that event                      |
| Confidence          | reliability of the incident classification / evidence interpretation |

Evidence score, confidence, and risk are **not** interchangeable.

## Input

Phase 2C consumes `CorrelatedEvidenceGroup` objects from Phase 2B
(`backend/app/intelligence/correlation.py`). Each group carries:

- `zone_id` — spatial scope;
- `start_time` / `end_time` — evidence-span bounds;
- `anomalies` — preserved `AnomalyResult`s (original z-scores, per-metric
  direction, reasons);
- `signal_types` — distinct metrics involved;
- anomaly magnitude — √-compressed mean |z| used in the evidence score;
- `temporal_coherence` — how fully the group's timestamps fill its span;
- `persistence_minutes` — duration of the anomaly span;
- `citizen_reports` — preserved reports (category, severity, description,
  status);
- `evidence_score` — the Phase 2B correlation score.

Zone metadata (`Zone.estimated_population`, from the simulation) is available
as **simulated/estimated** population context for impact estimation.

## Incident Model

Proposed incident structure (design contract only; implementation in Phase
2C-B):

| field                        | purpose                                          |
| ---------------------------- | ------------------------------------------------ |
| `incident_id`                | deterministic, stable identifier                 |
| `zone_id`                    | affected zone                                    |
| `incident_type`              | from the MVP taxonomy below                      |
| `status`                     | lifecycle state (DETECTED → … → RESOLVED)        |
| `severity`                   | LOW/MEDIUM/HIGH/CRITICAL from risk bands         |
| `risk_score`                 | 0–100, from the documented risk formula          |
| `confidence`                 | 0–1, reliability of the assessment               |
| `start_time`                 | first evidence timestamp                        |
| `last_updated`               | when the assessment last changed                 |
| `estimated_affected_population` | simulated/estimated, from zone metadata      |
| `contributing_signals`       | signal-level findings feeding the incident       |
| `evidence`                   | the originating `CorrelatedEvidenceGroup`       |
| `explanation` / `reason`     | deterministic, human-readable reasoning chain    |

This is the contract that Phase 2C-B implemented (`Incident`, `RiskFactors`,
`IncidentAssessment`, `IncidentAssessor`; see the Implementation section).

## Incident Types

Small, extensible MVP taxonomy:

- `WATER_LOSS`
- `PRESSURE_ANOMALY`
- `WATER_QUALITY`
- `SUPPLY_DISRUPTION`
- `UNKNOWN`

The type is **inferred from correlated evidence** (signal types, deviation
directions, report categories) and must **never depend on the simulation
scenario name**. The engine does not know scenarios.

For the Zone B golden scenario the evidence pattern is consistent with a
potential water-loss / service-loss event:

- pressure **decreases** (anomalous low pressure readings);
- inflow flow **increases** (sustained above-expectation flow);
- consumption **decreases** (delivery below expected demand);
- water quality **decreases** (deviation below expected).

Language is deliberately qualified: the system reports that the **evidence is
consistent with a potential water-loss event**. It does **not** prove a
physical pipe rupture. Causality attribution is an operator/AI-interpretation
concern, not a deterministic claim.

## Incident Lifecycle

```
DETECTED
   ↓
INVESTIGATING
   ↓
ASSIGNED
   ↓
RESOLVED
```

- **DETECTED**: a qualifying evidence group promoted to incident; awaiting
  operator attention.
- **INVESTIGATING**: operator acknowledging and examining evidence (deterministic
  guidance available).
- **ASSIGNED**: an operator responsible for the incident is designated.
- **RESOLVED**: closed after human-confirmed disposition.

Transitions between states are operator/actor driven
(`DETECTED → INVESTIGATING → ASSIGNED → RESOLVED`); Phase 2C-A only documents
the states. The platform is decision support and never mutates states on its
own outside a documented, auditable transition rule.

## Incident Qualification

Not every anomaly — or even every correlated evidence group — becomes an
incident. Qualification uses **configurable evidence thresholds**, not
scenario-specific hardcoding.

Initial design target:

```
evidence_score >= 0.50  →  candidate / actionable incident
```

This threshold is **explicitly provisional**:

- it lives in `IncidentConfig`-style configuration (`qualification_threshold`);
- it was calibrated against normal, golden, and borderline scenarios during
  Phase 2C-B and **retained at 0.50** for the MVP;
- **0.50 is not presented as a scientifically established universal
  threshold.** It is a starting point to be tuned with measured data.

## Risk vs Evidence

The Phase 2B `evidence_score` is **not** reused as a risk score. They answer
different questions:

- **Evidence / correlation score**
  > "How strongly do the observations support a common event?"
- **Risk score**
  > "How consequential could the event be?"
- **Confidence**
  > "How reliable is the resulting classification / assessment?"

Strength of evidence and magnitude of consequence are independent dimensions:
a highly certain leak in a low-population zone can be lower-risk than an
uncertain quality event in a dense zone.

## Risk Factors

Five normalized factors, each in `[0, 1]`, proposed for the MVP:

1. **Evidence strength** — carries the Phase 2B correlation strength into
   risk (transformed, not copied as a substitute for the other factors).
2. **Anomaly severity** — magnitude of deviations (e.g. mean |z| of
   contributing anomalies).
3. **Persistence** — how long the deviation has lasted (duration vs a
   calibration horizon).
4. **Estimated impact** — normalized consequence using affected-population /
   supply-relevance of the zone.
5. **Citizen context** — community signal (number/category/severity of
   citizen reports), bounded so sentiment cannot dominate.

Each factor must be computed deterministically and independently testable.

## Risk Formula

Proposed transparent weighted formula (MVP):

```
risk_normalized =
    0.30 × evidence_strength
  + 0.20 × anomaly_severity
  + 0.20 × persistence
  + 0.20 × impact
  + 0.10 × citizen_context

risk_score = 100 × risk_normalized
```

Constraints:

- all weights sum to **1.0**;
- the formula is a **proposed MVP design**, not scientifically validated;
- it will be validated and calibrated against normal, golden, and borderline
  scenarios during Phase 2C-B;
- the formula lives in code and is documented (per project hard constraint —
  never generated by an LLM).

## Severity

Risk score bands (configurable):

| risk_score | severity    |
| ---------- | ----------- |
| 0–24       | LOW         |
| 25–49      | MEDIUM      |
| 50–74      | HIGH        |
| 75–100     | CRITICAL    |

Operational meaning (decision-support guidance, **not** autonomous commands):

| severity  | operator intent     |
| --------- | ------------------- |
| LOW       | monitor             |
| MEDIUM    | investigate         |
| HIGH      | prioritize response |
| CRITICAL  | immediate escalation |

These are advisory labels for the operator dashboard, never instructions for
automatic action.

## Estimated Impact

`estimated_affected_population` is taken from zone metadata
(`Zone.estimated_population`) where available.

- It is **simulated/estimated data** in the MVP and must not be represented as
  authoritative real-world population data.
- The impact factor is normalized **transparently** (e.g. population relative
  to a calibration reference, with a documented bounded curve).
- **Missing impact data is handled safely**: unknown population must not crash
  evaluation or silently blow up the score — the factor falls back to a
  documented neutral value and the reason records that impact data was absent.

## Confidence

Confidence is a **distinct** quantity:

- it is **not** simply equal to the risk score;
- it is **not** simply equal to the evidence score.

Confidence reflects the **reliability/strength of the available evidence and
of the resulting classification** — e.g. how unambiguous the signal mix and
directions are, how complete the evidence is (multiple metrics corroborating
one expected pattern, reports consistent with the type), and how stable the
assessment is over time.

The exact formula was **finalized in Phase 2C-B** (see Confidence in the
Implementation section) after examining the available evidence fields and
calibrating against the scenario set. This document fixes the semantic
contract: confidence measures assessability/reliability, separately from how
big the consequence might be (risk) and how strong the correlation is
(evidence).

## Golden Zone B Assessment

Expected qualitative path for the golden scenario:

```
Zone B
 → pressure anomaly        (below expected)
 → flow anomaly            (above expected)
 → consumption anomaly     (below expected)
 → quality anomaly         (below expected)
 → citizen reports         (low_pressure / supply_disruption)
 → strong correlated evidence
 → potential WATER_LOSS incident
 → deterministic risk calculation
 → severity band
```

Measured Phase 2B golden context (used for calibration, not as a claim of
final output):

- evidence score ≈ **0.985**
- **4** signal types
- **89** anomalies
- **12** citizen reports
- **345-minute** persistence
- coherence = **1.0**

Mapping notes:

- The evidence score is *not* translated into a confidence percentage; the
  two are defined separately above.
- No final risk score or severity is invented here — values come from
  implementation + calibration in Phase 2C-B (see the Implementation section
  for the measured golden outcome).

## Normal Scenario

A normal simulation must **not** generate strong actionable incidents.

Because Phase 2A operates at signal level, isolated 3-sigma anomalies are
expected in healthy data (~1% of measurements). Phase 2B already reduces the
significance of isolated unrelated anomalies (they form weak, low-diversity,
low-persistence groups). Phase 2C therefore **requires sufficiently strong
correlated evidence** to qualify an incident (see Incident Qualification),
which keeps single/sporadic anomalies below the actionability line.

## Safety / Operational Boundary

**NEER is decision support.**

NEER does **not**:

- automatically control valves or pumps;
- shut down infrastructure;
- dispatch emergency crews;
- make irreversible operational decisions.

Human operators remain responsible for action. All outputs — incident,
risk, severity, classification, recommendations — are advisory evidence and
guidance presented to a human.

## Explainability

Every incident preserves its full reasoning chain:

- contributing signals (which anomalies, which metrics, directions);
- relevant anomaly results (original z-scores, expected/observed);
- correlation evidence (the source `CorrelatedEvidenceGroup`);
- risk factors (all five normalized components);
- risk calculation (formula application, weights, bands);
- classification reasoning (why this `incident_type`).

The future UI must be able to answer:

> "Why did NEER create / prioritize this incident?"

## Future AI Boundary

LLM/AI integration comes **after** deterministic incident and risk generation.

The future AI layer may:

- summarize the incident in natural language;
- explain the evidence;
- suggest investigation actions;
- suggest response options;
- communicate uncertainty.

The AI **must** consume structured incident/risk context (the deterministic
objects above) — never raw sensor streams smuggled via the frontend.

The AI **must not**:

- calculate raw anomaly statistics;
- secretly determine numerical risk;
- override deterministic risk logic;
- autonomously control infrastructure.

## Limitations

- The network is a **simulation**; results are not live telemetry.
- Population data is **estimated**, never authoritative.
- Statistical thresholds (evidence qualification, severity bands) require
  **calibration** against the scenario set.
- Evidence/risk weights are **MVP design choices**, not validated science.
- Scenario coverage is limited (golden + normal; borderline cases must be
  added for calibration).
- Correlation does **not** prove physical causality; "consistent with a
  potential event" is the honest ceiling of the deterministic layer.

## Implementation (Phase 2C-B)

Live code: `backend/app/intelligence/incident.py` (exported through
`backend/app/intelligence/__init__.py`). Consumes Phase 2B evidence directly;
module-scope helper wrappers `assess_group` / `assess_groups` pair an
`Incident` with its `IncidentAssessment` (qualification verdict + reason + the
assembled incident).

### Pipeline position

```
Simulation → Anomaly Detection → Correlated Evidence
    → assess_groups(groups, zones)
        → qualification → classification → risk factors → risk → severity → confidence
    → IncidentAssessment tuple (0..n qualified incidents)
        → AI-assisted explanation / recommendation (later)
```

### Determinism

- No clocks in the engine. `last_updated` = `group.end_time`; `start_time` =
  `group.start_time`.
- `incident_id = "INC-{zone_id}-{start_time:%Y%m%dT%H%M%SZ}"` — stable,
  reproducible.
- `assess_many` sorts by `(start_time, zone_id, group_id)` so identical input
  (any order) yields an identical tuple; every object is a frozen dataclass.
- New incidents always begin in `status = DETECTED` (lifecycle advances are an
  operator/actor concern; the engine never mutates state on its own).

### Qualification

```
qualified = isfinite(evidence_score) and evidence_score >= qualification_threshold
```

- `qualification_threshold = 0.50` (configurable in `IncidentConfig`).
- Below-threshold or non-finite evidence → `qualified = False`, `incident =
  None`, and the reason states "does not exceed evidence threshold <X>".
- This is a **candidate**, not a mandate: severity/risk are advisory labels.

### Classification (deterministic, scenario-agnostic)

First matching rule wins; mean signed z per metric is compared against
`classification_z_threshold = 3.0`. The engine never inspects scenario names
(verified by tests) and reports qualified direction language only:

| incident_type      | signature (mean z vs +3 / −3)                            |
| ------------------ | -------------------------------------------------------- |
| `WATER_LOSS`       | pressure below AND flow above AND consumption below      |
| `SUPPLY_DISRUPTION`| consumption below AND (flow below OR a `supply_disruption` citizen report) |
| `PRESSURE_ANOMALY` | only `pressure` deviates (either direction)              |
| `WATER_QUALITY`    | only `quality` deviates (either direction)               |
| `UNKNOWN`          | any other deviation pattern / no deviation               |

`classification_reason` uses qualified wording, e.g. *"sustained low pressure,
above-expectation flow, and below-expectation consumption in zone B are
consistent with a potential water-loss event."* The engine never claims proven
physical failure. `classification_support` = fraction of contributing
anomalies whose metric/direction match the type signature (0 for `UNKNOWN`).

### Risk factors (each in `[0, 1]`, independently testable)

| factor             | computation (configurable bounds)                        |
| ------------------ | -------------------------------------------------------- |
| evidence_strength  | `clamp01(evidence_score)`                                |
| anomaly_severity   | `clamp01(mean_abs_z / 12)`                               |
| persistence        | `clamp01(persistence_minutes / 360)`                     |
| impact             | `clamp01(population / 50_000)`, fallback **0.5** when population missing |
| citizen_context    | `min(1, reports/10) × (0.5 + 0.5 × max_report_severity)`; severity weights low 0.4 / moderate 0.7 / high 1.0, unknown fallback 0.6 |

### Risk formula (in code, documented, never LLM-derived)

```
risk_normalized =
    0.30 × evidence_strength
  + 0.20 × anomaly_severity
  + 0.20 × persistence
  + 0.20 × impact
  + 0.10 × citizen_context

risk_score = round(100 × risk_normalized, 2)   # bounded [0, 100]
```

Weights sum to 1; `IncidentConfig` validates weight length/sum ≥ 0, severity
band ordering, and the citizen-severity mapping.

### Severity bands

`severity_from_risk` maps `risk_score` through configurable thresholds
(default `(25, 50, 75)`):

| risk_score | severity   | operator intent     |
| ---------- | ---------- | ------------------- |
| 0–24       | LOW        | monitor             |
| 25–49      | MEDIUM     | investigate         |
| 50–74      | HIGH       | prioritize response |
| 75–100     | CRITICAL   | immediate escalation |

### Confidence (reliability of the assessment, distinct from risk & evidence)

```
confidence =
    0.40 × evidence_score
  + 0.25 × signal_diversity
  + 0.15 × temporal_coherence
  + 0.20 × classification_support
```

- Rises with stronger, more diverse, more complete evidence; falls when
  evidence is ambiguous (`UNKNOWN` → support 0).
- Not a calibrated probability; it measures how assessable the evidence is.

### Golden Zone B measured outcome (seed 42, ref seed 99)

Exactly **one** incident qualifies (zone B):

- type `WATER_LOSS`, status DETECTED, population 32 000
- risk_score ≈ **91.52** → **CRITICAL**
- confidence ≈ **0.9918**
- factors ≈ (evidence 0.985, severity 1.0, persistence 0.958, impact 0.64,
  citizen 1.0)
- All other golden groups and **all normal-scenario groups** (seed 100, max
  evidence 0.365) are rejected → zero incidents in a healthy network.

### Field notes / edge behavior

- `estimated_affected_population` is `Zone.estimated_population` or `None`
  when the zone is unknown / zones skipped; missing data never crashes and
  falls back to the documented neutral impact factor.
- Groups with no anomalies or missing/non-finite anomaly z-scores degrade
  factors safely (`severity 0.0`, `UNKNOWN`) and remain fully explainable.
- These values are **simulated/estimated and calibrated**, not authoritative
  real-world risk figures.

### Tests

`backend/tests/test_incident_risk.py` — 33 tests covering the model, the
qualification threshold and its configurability, all five classification
routes and scenario-name independence, population/missing-population handling,
each factor normalization, the exact risk formula and weight validation,
0–100 bounding, severity boundaries, confidence semantics, explainability,
the golden / normal / zone-isolation pipelines, determinism, empty and
malformed input, and the architectural guards (no LLM/API, no FastAPI/db).