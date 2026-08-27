# AI Context & Output Contract

> Phase 3-A defined the DESIGN contract; Phase 3-B1 implemented the data layer
> (context/output schemas + `AIProvider` interface); Phase 3-B2 implemented the
> concrete Gemini provider behind that interface. This document defines the
> contract between the deterministic NEER intelligence core and the AI
> explanation/recommendation layer, and records implementation status.

## Implementation Status (Phase 3-B1)

**Implemented** (all deterministic; zero LLM/network dependency):

- context schema — `IncidentAIContext` + sections (`incident`, `evidence`,
  `risk`, `classification`)
  in `backend/app/intelligence/ai_context.py`;
- context construction — `build_ai_context(incident, correlated_evidence=None)`
  (deterministic projection from Phase 2C `Incident`, no clocks/random);
- context serialization — `serialize_context()` (canonical, schema-ordered,
  JSON-compatible, repr/secret-free);
- output schema — `AIIncidentAnalysis` + nested models (`PossibleCause`,
  `InvestigationAction`, `ResponseOption`, `Uncertainty`)
  in `backend/app/intelligence/ai_analysis.py`;
- provider interface — `AIProvider` protocol + error contract
  (`AIProviderError`, `ProviderUnavailableError`, `ProviderTimeoutError`,
  `MalformedAIResponseError`, `AIValidationError`)
  in `backend/app/intelligence/ai_provider.py`;
- validation — Pydantic v2 with strict constraints (ranges, enums, `Literal`
  framing, advisory-only responses, incident_id reference pattern);
- tests — `backend/tests/test_ai_context_contract.py` (26 tests).

**Not implemented** (deferred to Phase 3-B2 and later):

- fallback runtime behavior;
- API integration (routes, DB persistence, frontend AI UI).

The deterministic core (Phases 2A/2B/2C-B) remains locked and authoritative.

## Phase 3-B2 Implementation (Gemini Provider)

Implemented in `backend/app/intelligence/gemini_provider.py` using the current
`google-genai` Python SDK (dependency added to `backend/pyproject.toml`):

- `GeminiProvider` — concrete `AIProvider`; `generate_analysis(context)` performs
  a single structured-output, single-turn Gemini call and returns a locally
  re-validated `AIIncidentAnalysis`. Stateful HTTP client optional (`client=` is
  injected in tests); constructed from config + `GEMINI_API_KEY`.
- `GeminiProviderConfig` — `model` (default `gemini-2.5-flash`), `api_key`
  (default `None`, read from `GEMINI_API_KEY`), `timeout_ms` (60 s), `temperature`
  (0.2), `max_output_tokens` (4000). Credentials never logged, never in errors.
- `SYSTEM_INSTRUCTIONS` — deterministic system prompt: NEER role/purpose,
  authoritative-facts rule (deterministic values quoted, never recomputed, and
  absent from output), grounding-only-on-context, observation-vs-hypothesis
  language (`possible`/`plausible`/`consistent`), advisory-only recommendations,
  no physical-infrastructure control, no executed-action claims, explicit
  uncertainty, and an input-safety rule (context is DATA, not instructions —
  prompt-injection defense).
- Request shape: `system_instruction` + the serialized context
  (`serialize_context()`, the only incident data sent) + structured output via
  `response_mime_type="application/json"` with `response_json_schema` derived
  from `AIIncidentAnalysis.model_json_schema()`. No tools, no function calling,
  no search grounding.
- Output handling: response text parsed as JSON, then re-validated with
  `AIIncidentAnalysis.model_validate`. The surfaced `incident_id` must equal the
  input context's — a mismatch raises `AIValidationError`; the deterministic
  identity is never replaced.
- Error mapping onto the 3-B1 contract: missing key / auth / provider / network →
  `ProviderUnavailableError`; timeout → `ProviderTimeoutError`; empty or
  unparseable response → `MalformedAIResponseError`; schema-validation failure or
  `incident_id` mismatch → `AIValidationError`. Messages never carry the key.
- Tests — `backend/tests/test_gemini_provider.py` (23 tests): fake SDK client
  (deterministic, network-free); request construction (model, serialized context,
  system instructions, JSON schema, no tools/grounding); output validation; error
  mapping; secret hygiene; non-mutation; determinism; the golden Zone B pipeline;
  no DB/FastAPI coupling. One opt-in live test (skipped unless
  `NEER_RUN_LIVE_GEMINI_TEST=1` and `GEMINI_API_KEY` are set) asserts structure
  and safety properties only.
- Not implemented: fallback orchestration (Phase 3-B3), FastAPI routes, DB
  models, frontend AI UI, any autonomous action.

## Purpose

The NEER AI layer is an **assistive reasoning and communication layer** placed
**after** deterministic anomaly detection, correlation, and incident/risk
assessment:

```
Simulation → Anomaly Detection → Correlation → Incident Assessment
    → (deterministic Incident objects)
    → AI layer: explanation, interpretation, recommendations  [Phase 3-B2]
    → operator
```

The deterministic core remains authoritative for:

- measurements (observed values)
- anomaly scores (z-scores, status)
- correlation (groups, evidence score, coherence, persistence)
- incident classification
- risk score
- severity
- confidence

The AI layer provides:

- explanation / summarization
- evidence interpretation
- possible contributing causes
- investigation recommendations
- response options
- uncertainty communication

**The AI must not silently modify any deterministic result.** It may flag
discrepancies, express uncertainty, or recommend verification — it never
overwrites. NEER is decision support; the AI is advisory text on top of the
deterministic engine, never a replacement for it.

---

## AI Input Contract

### Conceptual object: `IncidentAIContext`

The future AI provider receives a **structured, derived context object**, built
from the deterministic Phase 2C output. Field names below align with the
existing models (see `backend/app/intelligence/incident.py` and
`correlation.py`).

Where the future layer needs information the deterministic pipeline does not
currently produce, it is documented here as a **future addition** and is not
invented.

| section        | source model / field                 | notes                                              |
| -------------- | ------------------------------------ | -------------------------------------------------- |
| **incident**   | `Incident` (Phase 2C-B)              | the deterministic record the AI explains           |
|                | `incident_id`                        | e.g. `INC-B-20260101T060000Z`                      |
|                | `zone_id`                            | spatial scope                                      |
|                | `incident_type`                      | `IncidentType` enum value                          |
|                | `status`                             | `IncidentStatus` enum value                        |
|                | `severity`                           | `SeverityLabel` enum value                         |
|                | `risk_score`                         | 0–100 deterministic score                          |
|                | `confidence`                         | deterministic assessment-confidence in [0, 1]      |
|                | `start_time` / `last_updated`        | ISO-8601 datetimes (deterministic)                 |
|                | `estimated_affected_population`      | int or `null` (from zone metadata)                 |
| **evidence**   | `Incident.evidence` (`CorrelatedEvidenceGroup`) |                          |
|                | `contributing_signals`               | `ContributingSignal` tuples: `metric`, `direction`, `anomaly_count`, `mean_z`, `mean_abs_z` |
|                | `evidence_score`                     | correlation score                                  |
|                | `temporal_coherence`, `spatial_coherence` | group coherence values                        |
|                | `signal_diversity`                   | distinct metric mix vs known metrics               |
|                | `persistence_minutes`                | duration of the evidence span                      |
|                | `sensor_anomaly_count`               | anomaly count in scope                             |
|                | citizen-report summaries             | count + per-category/severity aggregation, not raw bodies if separable |
| **risk**       | `Incident.risk_factors` (`RiskFactors`) | five normalized components                      |
|                | `evidence_strength`                  | in [0, 1]                                          |
|                | `anomaly_severity`                   | in [0, 1]                                          |
|                | `persistence`                        | in [0, 1]                                          |
|                | `impact`                             | in [0, 1]                                          |
|                | `citizen_context`                    | in [0, 1]                                          |
|                | final deterministic `risk_score`     | duplicate of `incident.risk_score` for readability |
| **classification** | `Incident.incident_type`         | the deterministic type                             |
|                | `Incident.classification_reason`     | what the engine asserts (qualified wording)        |
|                | classification support               | derivable from `classification_support()`; future addition if shipped as a standalone field |

### Alignment rule

- Reuse the actual field names from `Incident`, `RiskFactors`,
  `ContributingSignal`, `CorrelatedEvidenceGroup`, `AnomalyResult`, and
  `CitizenReport`.
- Any field that cannot be derived from the existing pipeline today must be
  labeled **(future addition)** in the context schema — never silently added to
  the deterministic core.

---

## Raw Data Policy

The AI receives **structured summaries**, not unrestricted raw streams.

Allowed in context:

- relevant measurement values (subset scoped to the incident + zone)
- anomaly summaries (metric, direction, magnitude, count, time bounds)
- aggregate statistics (means, counts, z-statistics already computed deterministically)
- timestamps (incident span)
- zone information (zone_id, population estimate)
- citizen-report summaries (category/severity/count; descriptions only as needed)

Not allowed in context:

- unnecessary historical data unrelated to the incident
- data from unrelated zones
- secrets, credentials, API keys, passwords, database connection strings
- internal system prompts or provider instructions
- provider credentials of any kind

The context is **scoped, minimized, and derived**. Size and cardinality limits
(list lengths, report bodies, anomaly samples) are enforcement points for the
future serialization layer.

---

## Authoritative vs Interpretive Data

This distinction is mandatory and is preserved through the whole pipeline,
including the UI.

### Authoritative (deterministic) — treated by the AI as facts supplied by NEER

- observed measurements
- anomaly scores (z-scores, status)
- evidence/correlation score
- `incident_type` from deterministic classification
- `risk_score`
- `severity`
- `confidence`
- `estimated_affected_population`
- timestamps

The AI must **quote** these, never recompute or replace them.

### Interpretive (AI-generated) — advisory

- explanation / summary
- possible causes
- investigation recommendations
- response options
- uncertainty narrative

The AI may reason *about* the authoritative fields but must not alter them.

---

## AI Output Contract

### Conceptual object: `AIIncidentAnalysis`

The provider returns a structured, schema-validated object (`AIIncidentAnalysis`,
implemented in Phase 3-B1, produced by the Phase 3-B2 Gemini provider):

| field                     | type                      | meaning                                        |
| ------------------------- | ------------------------- | ---------------------------------------------- |
| `incident_id`             | string                    | must match the input incident's id             |
| `summary`                 | string                    | plain-language one-paragraph overview          |
| `evidence_interpretation` | string / array            | how the deterministic evidence reads           |
| `possible_causes`         | array of cause objects    | hypotheses, each framed as possible/plausible/consistent |
| `investigation_actions`   | array of recommendation objects | ordered, advisory, evidence-grounded      |
| `response_options`        | array of option objects   | operator suggestions, advisory only            |
| `uncertainty`             | structured object         | what is supported / uncertain / needed         |
| `safety_notes`            | array of strings          | decision-support boundaries, "no autonomous action" reminder |

Each `possible_cause` entry:

```jsonc
{
  "cause": "possible pipeline leak",
  "framing": "consistent with evidence",   // possible | plausible | consistent | (never confirmed)
  "supporting_evidence": ["pressure below expected", "inflow above expected"],
  "notes": "not independently verified"
}
```

Each recommendation entry:

```jsonc
{
  "action": "inspect pressure-control valves in zone B",
  "category": "inspect_pressure_infrastructure",
  "priority": 1,                            // advisory ordering
  "rationale": "grounded in pressure anomaly + flow increase"
}
```

Required fields must validate; extra unknown fields are subject to the schema
policy (see Validation). **Nothing in the output is a determinative fact** until
checked against the schema and never accepted as an authoritative replacement.

---

## Possible Causes — Causal Language Rules

The AI may suggest hypotheses, e.g.:

- possible pipeline leak
- pressure regulation issue
- sensor anomaly / faulty instrumentation
- localized supply disruption
- water-quality contamination source

Causal language must distinguish **"consistent with"** from **"confirmed"**:

- GOOD: *"Pressure decline combined with increased inflow and reduced
  consumption is consistent with possible water loss."*
- BAD: *"The pipeline has ruptured."*

Rules:

1. Never state physical causality as established unless authoritative data
   independently confirms it (the deterministic core never does).
2. When the evidence is compatible with more than one cause, the AI must
   explicitly say so and list the competing hypotheses.
3. Every hypothesis must trace back to supplied evidence (cite the relevant
   signals/reports).
4. "Unknown cause" is always an acceptable, explicit answer.

---

## Investigation Recommendations

Advisory action categories the AI may propose:

- inspect the relevant zone
- verify sensor readings (instrumentation check)
- compare neighboring measurements / neighboring zones
- inspect pressure/flow infrastructure
- review recent maintenance records
- verify citizen reports

Constraints:

- actionable and concrete, not generic fillers
- ordered/prioritized where useful (`priority` in the output schema)
- advisory — never a command
- grounded in the supplied evidence; the rationale must cite context
- never claim an external system was checked unless the context explicitly
  contains that information (no invented "GPS data shows…", "SCADA confirms…")

---

## Response Options

Response options are suggestions **for a human operator**, e.g.:

- verify the incident locally
- inspect the affected network section
- notify the relevant operations team
- increase monitoring of the zone
- prepare public communication

The AI must **not**:

- issue commands to infrastructure
- claim an action was executed
- dispatch emergency services
- shut valves or pumps
- alter network controls

Wording convention:

> "Consider…" / "An operator may…" / "Recommended next verification step…"

---

## Uncertainty

The AI must communicate uncertainty explicitly via the structured `uncertainty`
field:

- **supported** — what the deterministic evidence strongly supports (e.g., a
  multi-signal deviation pattern)
- **uncertain** — what remains ambiguous (cause attribution, later impact)
- **additional_info** — what would help distinguish hypotheses (e.g.,
  "compare neighboring-zone flow", "confirm report severity")

Critical rules:

- `confidence` (deterministic) is **not** a calibrated probability. Do not say
  *"there is a 99% chance of a pipeline rupture"* unless future calibration
  genuinely supports that statement.
- Map confidence qualitatively ("high/average/low assessability") at most, or
  quote the deterministic value without probability semantics.
- Always distinguish *strength of evidence* from *certainty of cause*.

---

## AI Must Not Recalculate Numbers

Hard architectural rule. The AI must **not**:

- recalculate risk
- recalculate severity
- recalculate anomaly scores (z-scores)
- recalculate correlation/evidence scores
- invent measurements
- alter population estimates
- change timestamps
- change `incident_type`
- override deterministic classification

The deterministic engine remains authoritative. If the AI disagrees with a
deterministic result, it may (a) express uncertainty, or (b) flag the
discrepancy for the operator — it cannot overwrite the result. Enforced by:

- prompt strategy (explicit instructions), and
- output validation (authoritative fields are never accepted as replacements —
  see Validation).

---

## Prompt Strategy

Future structure — never a blind concatenation of raw logs:

```
SYSTEM INSTRUCTIONS
+
STRUCTURED INCIDENT CONTEXT   (IncidentAIContext, serialized to schema)
+
OUTPUT SCHEMA                 (AIIncidentAnalysis JSON schema)
```

The system instructions explicitly tell the model:

- act as an operational **decision-support** assistant for a water network
- use only the supplied context; do not invent data
- distinguish observations (facts) from hypotheses (interpretation)
- do not fabricate measurements, zone data, or citizen reports
- do not recalculate any deterministic value (risk, severity, z-scores, scores)
- do not claim any action was executed
- do not issue autonomous infrastructure commands (no valve/pump shutdowns)
- communicate uncertainty explicitly
- fit the required structured output (field names, types, constraints)

The prompt is constructed from schema-driven templates, not free-form log
dumps. **Implemented in Phase 3-B2:** `SYSTEM_INSTRUCTIONS` (deterministic
constant) + `serialize_context()` as the single data input + the Pydantic JSON
schema as `response_json_schema`.

---

## Provider Abstraction

Intended structure:

```
AIProvider            (interface / protocol)
    ↓
generate_analysis(context: IncidentAIContext) -> AIIncidentAnalysis
```

Properties:

- the rest of NEER depends on `AIProvider`, **not** on Gemini-specific APIs
- a concrete provider (e.g., Gemini, or a local/mock provider) is swappable
  without changing the deterministic intelligence engine
- the deterministic engine never touches the provider
- `generate_analysis` takes the validated, serialized context and returns the
  validated analysis

For Phase 3-A this was an interface design only; Phase 3-B1 implemented the
protocol + error contract; Phase 3-B2 implements the concrete provider
(`gemini_provider.py`) and swappable-testing via an injected fake SDK client.

---

## Validation

The AI response is **untrusted generated content** until it passes schema
validation:

- malformed output (bad JSON, wrong types) → reject or handle safely
- missing required fields → reject (or fail to a defined fallback)
- unknown/extra fields → ignored or rejected per the schema policy (decided at
  implementation time; contract default: strict, unknown fields rejected)
- deterministic authoritative fields are **not accepted from the LLM** as
  replacements — a mismatch between the AI's quoted risk and the real
  deterministic risk is an AI error, not a correction
- structural checks: `incident_id` match, arrays where arrays are expected,
  bounded strings, no forbidden command vocabulary (e.g. "valve closed", "crew
  dispatched")

---

## Fallback

If the provider fails — unavailable, timeout, quota exceeded, malformed or
invalid output — NEER must still present the deterministic incident:

```
provider failure
    ↓
deterministic Incident remains available and unchanged
    ↓
fallback analysis:
    - deterministic incident summary (already deterministic)
    - evidence-based explanation template (deterministic)
    - "AI analysis unavailable" state
```

- AI failure must **not** make the incident disappear.
- The operator UI shows the incident regardless of AI health.
- Future tests must cover: missing provider, timeout, malformed response,
  quota/rate errors, and the deterministic incident surviving AI failure.
- Not implemented yet; planned for Phase 3-B3 (fallback orchestration).

---

## Security / Privacy

The AI context must never contain:

- API keys, passwords
- database credentials or connection strings
- internal secrets or provider credentials
- unnecessary PII
- unrelated incident data

Citizen reports should be **summarized/minimized** where possible (counts,
categories, severities) instead of passing raw bodies; descriptions are passed
only when required for explanation and are still subject to minimization.
Provider credentials live outside NEER's data path — the provider call site
(Phase 3-B2) reads `GEMINI_API_KEY` from the environment and never logs it.
Tests scan context payloads and provider behaviors for the absence of secrets.

---

## Golden Zone B Example

Deterministic context (measured, seed 42 vs reference seed 99):

| field                          | value           |
| ------------------------------ | --------------- |
| zone                           | B               |
| incident type                  | WATER_LOSS      |
| risk_score                     | 91.52           |
| severity                       | CRITICAL        |
| confidence                     | 0.9918          |
| evidence score                 | 0.985           |
| signal types                   | 4               |
| sensor anomalies               | 89              |
| citizen reports                | 12              |
| persistence                    | 345 minutes     |
| estimated affected population  | 32 000          |

Intended AI style (example, not a required exact response):

> "The incident is consistent with a potential water-loss event because Zone B
> shows a sustained pressure decline alongside increased inflow and reduced
> consumption, supported by water-quality deviation and citizen reports."

Constraints demonstrated by this example:

- qualified causal language ("consistent with", "potential" — never "Pipeline
  rupture confirmed.")
- cites the supplied signals (pressure, inflow, consumption, quality, reports)
- identifies uncertainty and recommends verification (e.g., "verify sensor
  readings and inspect zone B pressure/flow infrastructure")
- reduces, rather than inflates, certainty

---

## Frontend Contract

Future UI must consume the **deterministic `Incident`** and the
**`AIIncidentAnalysis`** as **separate** objects:

- measured/deterministic facts render as facts (evidence score, risk,
  severity, confidence, signals)
- AI interpretation renders as interpretation (clearly labelled, e.g. a
  distinct "AI analysis" panel)
- recommendations render as advisory items with an operator-action affordance

The UI must not imply AI-generated hypotheses are authoritative facts. Example
visual treatment: deterministic data in the incident detail; AI content in a
collapsible/reasoned section marked "AI interpretation — advisory". Should one
source be absent (AI unavailable), the incident view still works.

---

## Testing Contract (future)

Documentation-level specification for tests a later phase implements:

- context serialization (fields, types, bounds)
- required context fields present
- absence of secrets in context payloads
- correct separation of authoritative vs AI fields (schema-level)
- structured output validation (good + malformed cases)
- malformed AI response handling
- missing AI provider
- timeout
- quota/rate failure
- fallback behavior (template + "AI analysis unavailable")
- hallucinated measurements detected/rejected
- attempted risk override rejected
- attempted severity override rejected
- attempted autonomous command rejected
- deterministic incident survives AI failure

None of these tests were added in Phase 3-A (design-only). Phase 3-B1
implements the validation-schema ground truth these tests build on (context
serialization, required fields, secret absence, authoritative/AI separation,
structured output validation via the Pydantic schemas). Phase 3-B2 lands the
provider-behavior tests for the Gemini provider — missing key, timeout, network
failure, malformed/invalid/mismatched responses, advisory enforcement — all
network-free via an injected fake SDK client, plus an opt-in live Gemini test
(`NEER_RUN_LIVE_GEMINI_TEST=1` + `GEMINI_API_KEY`). Fallback-behavior tests
(missing provider, quota/rate, deterministic incident surviving AI failure)
land with fallback orchestration in Phase 3-B3.

---

## Phase 3-A / 3-B1 / 3-B2 Scope Boundary

Implemented in Phase 3-A:

- this contract document only

Implemented in Phase 3-B1:

- AI context models (`IncidentAIContext`), construction, and serialization
- AI output models (`AIIncidentAnalysis`)
- `AIProvider` interface + error contract
- schema-validation tests

Implemented in Phase 3-B2:

- concrete Gemini provider (`gemini_provider.py`: `GeminiProvider`,
  `GeminiProviderConfig`, `SYSTEM_INSTRUCTIONS`)
- `google-genai` dependency, structured-output request (JSON schema),
  local re-validation, and `AIProviderError` mapping
- network-free provider tests (fake SDK client) + opt-in live Gemini test
- `GEMINI_API_KEY` handling (never logged/committed; missing → unavailable)

Not implemented (they land in Phase 3-B3 and later):

- fallback orchestration behind the `AIProvider` contract
- any FastAPI route / operator workflow
- PostgreSQL/persistence models
- frontend AI components
- any modification of simulation / baseline / detector / correlation / incident
  engines, the 3-B1 context/analysis/interface modules, or existing tests

The deterministic core remains locked, and the whole contract suite passes:
**131 tests** (108 prior + 23 Phase 3-B2), with the live Gemini test opting in
only via `NEER_RUN_LIVE_GEMINI_TEST=1` + `GEMINI_API_KEY`.