# Signal Correlation (Phase 2B)

## Scope

Phase 2B takes the signal-level anomalies of Phase 2A plus contextual citizen
reports and groups them into **correlated evidence groups**. That is all it
does: it never claims an incident exists, never computes risk or severity, and
uses no LLM. An evidence group is the input to *incident generation*
(later phase), which is where severity and risk get calculated.

> **Terminology.** A group states that several signals in one zone correlate
> in time and space — "correlated evidence suggests a possible common event".
> It is evidence, not a proven leak. The numeric strength of a group is the
> **`evidence_score`** (a correlation/coherence score), never a risk score.

Module: `backend/app/intelligence/correlation.py` (engine), consumed through
`app.intelligence.correlate_evidence`. It is deterministic, stateless-by-config,
and independent of the database, FastAPI, and the simulation's scenario
machinery.

> An **anomaly** is a single deviating measurement (Phase 2A). Correlation
> turns many like-timed same-zone anomalies into one evidence group; an
> incident appears only in a later phase.

## Why this method

Raw anomaly lists are noisy: healthy 3-sigma false positives (~1% of
measurements) are scattered across zones and times, while a real event raises
**multiple metrics in the same zone for hours** (golden Zone B: pressure, flow,
consumption and quality all deviate 06:00–11:45Z). The correlation problem is
therefore spatial+spatiotemporal grouping. Simson of alternatives:

- *Fixed global no spatial/ML clustering (DBSCAN, etc.)* — rejected:
  needs radius/epsilon tuning that has no physical meaning for this semantic and
  pulls in an external dependency for a rule scikit-learn cannot do better.
- *Simple fixed time bucket (e.g. one group per zone-hour)* — rejected:
  cannot express "one 6-hour persistent event" as a single group.
- *Threadlessly merging by manual offset rules* — same as fixed bucket.
- **Chosen: gap-based single-linkage clustering per zone.** It has a single,
  physically interpretable knob (the temporal window), keeps zones strictly
  disjoint by construction, and reproduces both outcomes we need — a long
  contiguous event stays one group, sporadic same-zone outliers stay separate.

Citizen reports are handled **after** sensor clustering (sensor-led): they can
strengthen an existing group but can never create one and, by design, contribute
at most their weight (15%) to the evidence score.

## Temporal window

`CorrelationConfig.temporal_window_minutes = 60`. Measurement cadence is 15
minutes. The golden incident produces *contiguous* anomalous coverage across all
04 metrics at that cadence (25 distinct timestamps, max intra-block gap 15
min), so a 60-min window tolerates up to three quiet slots without splitting a
sustained event, while any two unrelated same-zone anomalies are observed ≥
hours apart. Measured consequences on the seed-42/seed-100 runs:

- Golden Zone B stays one group (06:00–11:45Z) and one stray quality@17:00 in
  Zone B correctly splits into its own weak group (gap 315 min > 60).
- The normal run (seed 100) produces only single-anomaly groups.
- Two random golden Zone-A anomalies 30 min apart merge, but the resulting
  group scores 0.373 vs the incident's 0.985 — far below any threshold that
  would matter downstream.

**Caveat (documented, intentional):** clustering is single-linkage with the
configurable window; genuinely continuous 24/7 activity with no quiet hour
would chain into one group. Downstream incident logic must bound group
duration if that ever matters.

## Evidence score — formula (`app/intelligence/correlation.py`)

For each group:

| component | formula                                                    | weight |
| --------- | ---------------------------------------------------------- | ------ |
| magnitude | `min(√mean\|z\|, 4.0) / 4.0`                                | 0.30   |
| diversity | `min(1, #distinct metrics / 4)`                             | 0.25   |
| coherence | `min(1, #anomalous timestamps / (span_min // 15 + 1))`      | 0.15   |
| persistence | `min(1, anomaly_span_min / 360)`                          | 0.15   |
| reports   | `min(1, #attached reports / 10)`                            | 0.15   |

`evidence_score = Σ weight × component`. Weights live in
`CorrelationConfig.evidence_weights` and must sum to 1.0.

Rationale, grounded in measured data:

- **Magnitude** uses the √-compressed mean |z| (mean gold z ≈ 15), capped at
  4.0 so a single extreme reading cannot dominate (pressure saturation bound —
  see the Phase 2A limitation note).
- **Diversity** is capped at 1.0 (4 known metrics). Four metrics beat four
  pressure readings *of equal magnitude*; a weak multi-metric burst (A@10:30,
  score 0.373) stays far below a strong single-metric one would need to matter.
- **Coherence** measures how fully a group's anomaly timestamps fill its span;
  a sustained block scores 1.0, two isolated points far apart score ~0.
- **Persistence** uses the 6-hour incident horizon as reference; an isolated
  anomaly contributes 0, the golden block contributes ~0.96.
- **Reports** saturate at `report_cap = 10`; additional citizen calls add
  nothing, so public sentiment can inform a group but never override sensor
  evidence (bounded at 15% of the score). Categories/severity/description are
  preserved on the group for later incident context.

Calibrated scores (seed-42 golden / seed-100 normal):

| group                                  | score  | signal types | length |
| -------------------------------------- | ------ | ------------ | ------ |
| Golden Zone B (89 anomalies, 12 reports) | ~0.985 | 4            | 345 min |
| Golden stray Zone B quality@17:00       | ~0.34  | 1            | 0      |
| Golden Zone A random pair @10:30        | ~0.37  | 2            | 30 min |
| Normal zones (all single anomalies)     | ≤0.37  | 1            | 0      |

## Group model — `CorrelatedEvidenceGroup`

- `group_id` `CGE-{zone}-{seq}` (seq assigned deterministically after sorting
  by `(start_time, zone_id)`, independent of input order)
- `zone_id`, `start_time`/`end_time` (span the actual attached evidence),
- preserved input objects: `anomalies` (full `AnomalyResult`s with original
  z-scores) and `citizen_reports` (full `CitizenReport`s),
- interpretable fields: `signal_types`, `sensor_anomaly_count`,
  `citizen_report_count`, `signal_diversity`, `temporal_coherence`,
  `spatial_coherence` (1.0 — single-zone by construction), `persistence_minutes`,
- `evidence_score`, and `summary` (a fixed template sentence that says
  "correlated evidence suggesting a possible common event" — never "leak
  proven").

`CorrelationResult` also carries `unassigned_reports` (never dropped, never
turned into groups), total input counts, and the config used.

## Behaviour guarantees

- Zones never merge; every group and every member stays in one zone.
- Groups are sensor-led: ≥1 valid anomalous `AnomalyResult` (status
  `anomalous`, `is_anomalous`, finite z), else nothing.
- Non-anomalous, `insufficient_baseline`, `invalid`, blank-zone, and
  non-finite (NaN/±inf) anomalies are excluded safely and counted correctly.
- Deterministic: input order, report order, and cluster order cannot change the
  output (all sorted internally; group ids assigned post-sort).
- Empty inputs produce an empty `CorrelationResult` without raising.

## Golden Zone B reproducibility

Running the full pipeline (simulation → Phase 2A detection → correlation):

```python
from app.simulation import build_config, run_simulation
from app.intelligence import detect_anomalies, correlate_evidence

reference = run_simulation(build_config(seed=99, duration_hours=7 * 24.0))
incident = run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))

findings = detect_anomalies(reference.measurements, incident.measurements)
result = correlate_evidence(findings, incident.reports)

top = max(result.groups, key=lambda g: g.evidence_score)
assert top.zone_id == "B"
assert set(top.signal_types) == {"pressure", "flow", "consumption", "quality"}
assert top.citizen_report_count == 12 and top.sensor_anomaly_count >= 80
assert top.evidence_score >= 0.8
```

The reference-normal network and the incident target are independent seed
realizations; the engine never knows the scenario name.

## Next phase (NOT implemented)

Incident generation from evidence groups, severity/risk scoring, classification,
AI explanation and response recommendations, FastAPI routes, and PostgreSQL
persistence. The evidence score is deliberately not a risk score so Phase 2C can
own that definition.

## Usage

```python
from app.intelligence import CorrelationConfig, correlate_evidence

config = CorrelationConfig(temporal_window_minutes=60)   # defaults shown
result = correlate_evidence(anomalies, reports, config=config)
for group in result.groups:
    print(group.group_id, group.evidence_score, group.summary)
```

Tests (Phase 0 + 1 + 2A + 2B): `python -m pytest`