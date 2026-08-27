# Anomaly Detection (Phase 2A)

## Scope

Phase 2A is **signal-level** intelligence: for every measurement it computes a
baseline expectation and a normalized deviation. It does **not** create
incidents, does not correlate signals across metrics, does not score risk, and
does not use an LLM. Correlation and incident generation are Phase 2B. The
module is `backend/app/intelligence/` and is independent of the database,
FastAPI, and the simulation's scenario machinery.

> An **anomaly** is: a single measurement deviating unusually far from what its
> zone+metric normally looks like at that time of day. It is a *finding*, not
> an incident. A cluster of corroborated anomalies across metrics/time becomes
> an incident only in a later phase.

## Why this method

The Phase 1 simulator produces, per zone and metric, values that follow a
smooth **diurnal demand pattern** plus small Gaussian noise. Flow and
consumption fluctuate ~20–35% across the day, so any detector using the
configured nominal value as a constant expectation would systematically flag
the normal morning trough and evening peak (naive pseudo-z up to ~9.7 for a
perfectly normal early-morning flow reading).

A **time-of-day baseline** is the simplest method that matches the data's
structure: expected value varies by hour-of-day, estimated from a reference
*normal* measurement history. No time-series model is needed; this explicitly
is not a forecasting system.

Chosen over alternatives:

- *Constant nominal baseline* — rejected: biases against normal diurnal
  variation (measured failure mode above).
- *Robust (median/MAD) z-score* — same exposure to diurnal drift; reference
  data are clean, so the extra robustness buys nothing here.
- *ARIMA/ML forecasting* — rejected: over-engineering for a generator whose
  time structure is captured by bucket means.
- *Scikit-learn* — not used; hand-picked statistical analysis is sufficient
  and fully deterministic.

## Baseline strategy (`app/intelligence/baseline.py`)

For each `(zone_id, metric, time-of-day bucket)`:

- **expected** = mean of reference values in that bucket
- **dispersion** = sample standard deviation of reference values in that
  bucket, floored at `min_cv × expected` (default `min_cv = 0.01`) so zero or
  near-zero variance cannot produce infinite scores or division by zero.

Buckets are hour-of-day aligned to UTC (`bucket_minutes = 60`, must divide
1440). Using a **relative** dispersion floor (not per-metric absolute numbers)
keeps the knob dimensionless and the same across all four metrics.

Reference data: a normal (non-incident) simulation run, seeded distinctly from
the evaluated run so the reference and target are independent realizations of
the same normal process. In the tests: 7 days, seed 99. The detector itself
has no notion of "incident" — reference is simply "data the network is known to
be healthy in", target is "data to evaluate".

## Anomaly scoring (`app/intelligence/detector.py`)

For each measurement:

| field               | value                                        |
| ------------------- | -------------------------------------------- |
| `observed_value`    | the measurement                              |
| `expected_value`    | bucket mean from reference                   |
| `absolute_deviation`| `observed − expected`                       |
| `relative_deviation`| `(observed − expected) / expected`          |
| `anomaly_score`     | **z** = `absolute_deviation / dispersion`   |
| `is_anomalous`      | `|z| > z_threshold`                         |
| `status`            | `normal` / `anomalous` / `insufficient_baseline` / `invalid_measurement` |
| `reason`            | deterministic, human-readable explanation   |

Detection is **bidirectional**: both large positive and large negative
deviations are anomalous. Direction is reported in the reason (e.g. pressure
*below* expected, flow *above* expected) for later interpretation, but the
decision rule is symmetric around the expected value.

## Thresholds / configuration

- `DetectorConfig.z_threshold = 3.0` — the canonical 3-sigma rule. Healthy
  Gaussian noise trips it with probability ≈ 0.27% per measurement, so a normal
  1-day network (~1536 measurements) produces a handful of sporadic
  signal-level false positives (~1%). That is an accepted property of the
  method: incidents are recognized by *sustained, multi-metric, high-magnitude*
  elevation, which correlation (Phase 2B) will aggregate — never by a single
  measurement.
- `BaselineConfig.bucket_minutes = 60`
- `BaselineConfig.minimum_samples_per_bucket = 1` — minimum reference count to
  emit an expected value.
- `BaselineConfig.minimum_samples_for_dispersion = 2` — minimum reference count
  to measure dispersion.
- `BaselineConfig.min_cv = 0.01` — relative dispersion floor.

## Insufficient history / boundary conditions

The detector never guesses. When a score cannot be computed reliably it returns
`status = insufficient_baseline`, `anomaly_score = None`, `is_anomalous = False`
and a reason, for:

- no reference samples for the zone/metric/time bucket,
- fewer reference samples than `minimum_samples_per_bucket`,
- fewer reference samples than `minimum_samples_for_dispersion` (expected
  exists but dispersion cannot be measured),
- zero-variance buckets (handled via the `min_cv` floor instead).

`status = invalid_measurement` is returned for unsupported metrics and for
non-finite values (`nan`, `±inf`) — these must not silently produce scores.
Reference values that are non-finite are excluded from baseline statistics.

Zone and metric independence is structural: every slot is keyed by
`(zone_id, metric, bucket)`; a Zone A baseline is never consulted for Zone B,
and flow pressure statistics are never mixed.

## Golden Zone B reproducibility

Reference (normal): `run_simulation(build_config(seed=99, duration_hours=168))`
Target (incident): `run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))`

Observed in-window (06:00–12:00Z, 24 timestamps per metric) detection at
`z_threshold = 3.0`:

| metric      | mean z | flagged | direction |
| ----------- | ------ | ------- | --------- |
| pressure    | −32.0  | 24/24   | below expected |
| flow        | +7.6   | 22/24   | above expected |
| consumption | −12.5  | 23/24   | below expected |
| quality     | −4.2   | 20/24   | below expected |

89 of 96 incident-window measurements flagged; unaffected network (A/C/D and
Zone B outside the window) stays < 2% flagged. The 06:00/06:15 ramp-in samples
are legitimately borderline (z near threshold) — expected transition behaviour.

## Limitations

- Signal-level only; a single large reading is not an incident.
- The hourly bucket mean is a coarse expected shape; intra-bucket diurnal drift
  inflates dispersion slightly (conservative).
- ~1% healthy measurements trip the 3-sigma rule; downstream consumers must
  aggregate, not react to single flags.
- If reference and target are generated from the *same* seed, reference and
  target become identical and deviations collapse to ~0; always use an
  independent reference realization.
- Saturated incident readings (pressure/consumption pinned at simulator bounds)
  cap the observable z magnitude; later severity logic must not extrapolate
  beyond the observed margin.

## Usage

```python
from app.simulation import build_config, run_simulation
from app.intelligence import detect_anomalies

reference = run_simulation(build_config(seed=99, duration_hours=7 * 24.0))
target = run_simulation(build_config(seed=42, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",)))

findings = detect_anomalies(reference.measurements, target.measurements)
anomalies = [f for f in findings if f.is_anomalous]
```

Tests (Phase 0 + 1 + 2A): `python -m pytest`