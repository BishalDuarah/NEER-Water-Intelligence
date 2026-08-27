"""Phase 2A tests: baseline + signal-level anomaly detection.

The reference baseline is derived from a 7-day NORMAL simulation (seed 99).
Target data are independent 1-day runs (golden seed 42). The detector knows
nothing about scenario names; only the tests reference ZONE_B_SUPPLY_INCIDENT.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.intelligence import (
    STATUS_ANOMALOUS,
    STATUS_INSUFFICIENT,
    STATUS_INVALID,
    STATUS_NORMAL,
    AnomalyDetector,
    BaselineConfig,
    DetectorConfig,
    build_baseline,
    detect_anomalies,
)
from app.simulation import build_config, run_simulation
from app.simulation.models import Measurement

REFERENCE_SEED = 99
REFERENCE_DAYS = 7.0
GOLDEN_SEED = 42
METRICS = ("flow", "pressure", "quality", "consumption")


@pytest.fixture(scope="module")
def reference_measurements() -> list[Measurement]:
    result = run_simulation(
        build_config(seed=REFERENCE_SEED, duration_hours=REFERENCE_DAYS * 24.0)
    )
    return result.measurements


def _golden_incident():
    return run_simulation(
        build_config(seed=GOLDEN_SEED, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",))
    )


def _in_window(results, zone_id: str, metric: str, ws, we):
    return [
        r
        for r in results
        if r.zone_id == zone_id and r.metric == metric and ws <= r.timestamp < we
    ]


# --- A. Normal data ---------------------------------------------------------

def test_normal_data_generally_not_anomalous(reference_measurements) -> None:
    target = run_simulation(build_config(seed=100))
    results = detect_anomalies(reference_measurements, target.measurements)

    assert len(results) == len(target.measurements)
    # full coverage: every normal measurement is scored (no insufficient ones)
    assert all(r.status in {STATUS_NORMAL, STATUS_ANOMALOUS} for r in results)
    fraction = sum(r.is_anomalous for r in results) / len(results)
    assert fraction < 0.02, f"{fraction:.3f} of normal measurements flagged"


# --- B / C / D / E. Incident metric deviations ------------------------------

def test_strong_pressure_deviation_detected(reference_measurements) -> None:
    incident = _golden_incident()
    results = detect_anomalies(reference_measurements, incident.measurements)
    ws, we = incident.scenarios[0].window_start, incident.scenarios[0].window_end

    rws = _in_window(results, "B", "pressure", ws, we)
    assert len(rws) == 24
    mean_z = sum(r.anomaly_score for r in rws) / len(rws)
    assert mean_z < -10
    assert sum(r.is_anomalous for r in rws) / len(rws) >= 0.9


def test_strong_flow_deviation_detected(reference_measurements) -> None:
    incident = _golden_incident()
    results = detect_anomalies(reference_measurements, incident.measurements)
    ws, we = incident.scenarios[0].window_start, incident.scenarios[0].window_end

    rws = _in_window(results, "B", "flow", ws, we)
    assert len(rws) == 24
    mean_z = sum(r.anomaly_score for r in rws) / len(rws)
    assert mean_z > 5
    assert sum(r.is_anomalous for r in rws) / len(rws) >= 0.8


def test_consumption_deviation_detected(reference_measurements) -> None:
    incident = _golden_incident()
    results = detect_anomalies(reference_measurements, incident.measurements)
    ws, we = incident.scenarios[0].window_start, incident.scenarios[0].window_end

    rws = _in_window(results, "B", "consumption", ws, we)
    assert len(rws) == 24
    mean_z = sum(r.anomaly_score for r in rws) / len(rws)
    assert mean_z < -8
    assert sum(r.is_anomalous for r in rws) / len(rws) >= 0.8


def test_quality_deviation_detected_when_statistically_significant(reference_measurements) -> None:
    incident = _golden_incident()
    results = detect_anomalies(reference_measurements, incident.measurements)
    ws, we = incident.scenarios[0].window_start, incident.scenarios[0].window_end

    rws = _in_window(results, "B", "quality", ws, we)
    assert len(rws) == 24
    mean_z = sum(r.anomaly_score for r in rws) / len(rws)
    assert mean_z < -3.0
    assert sum(r.is_anomalous for r in rws) / len(rws) >= 0.5


# --- F. Bidirectional detection --------------------------------------------

def test_bidirectional_detection_incident_has_both_signs(reference_measurements) -> None:
    incident = _golden_incident()
    results = detect_anomalies(reference_measurements, incident.measurements)
    ws, we = incident.scenarios[0].window_start, incident.scenarios[0].window_end

    flow = _in_window(results, "B", "flow", ws, we)
    pressure = _in_window(results, "B", "pressure", ws, we)
    assert max(r.anomaly_score for r in flow) > 3.0      # positive deviations detected
    assert min(r.anomaly_score for r in pressure) < -3.0  # negative deviations detected
    assert any(r.is_anomalous and r.anomaly_score > 0 for r in flow)
    assert any(r.is_anomalous and r.anomaly_score < 0 for r in pressure)


def test_bidirectional_detection_synthetic(reference_measurements) -> None:
    # A measurement can be anomalous above OR below expected.
    ts = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    reference = [Measurement(ts, "X", "flow", 100.0, "m3/h") for _ in range(10)]
    detector = AnomalyDetector(build_baseline(reference))

    hi = detector.evaluate(Measurement(ts, "X", "flow", 104.5, "m3/h"))
    assert hi.is_anomalous and hi.anomaly_score > 0 and hi.status == STATUS_ANOMALOUS
    lo = detector.evaluate(Measurement(ts, "X", "flow", 95.5, "m3/h"))
    assert lo.is_anomalous and lo.anomaly_score < 0 and lo.status == STATUS_ANOMALOUS
    mid = detector.evaluate(Measurement(ts, "X", "flow", 100.0, "m3/h"))
    assert not mid.is_anomalous and mid.anomaly_score == 0.0 and mid.status == STATUS_NORMAL


# --- G. Time-aware baseline -------------------------------------------------

def test_time_aware_baseline_absorbs_diurnal_variation(reference_measurements) -> None:
    target = run_simulation(build_config(seed=GOLDEN_SEED))
    results = detect_anomalies(reference_measurements, target.measurements)

    morning = [r for r in results if r.zone_id == "B" and r.metric == "flow" and r.timestamp.hour < 6]
    assert len(morning) == 24
    for r in morning:
        assert not r.is_anomalous, f"diurnal morning trough flagged: {r.reason}"
        assert r.anomaly_score is not None and abs(r.anomaly_score) < 3.0

    # Proof the time awareness is necessary: naive comparison vs nominal base
    # (3100 m3/h) would flag the same normal early-morning points.
    profile = build_config().profiles["B"].flow
    naive_z = [
        abs(m.value - profile.baseline) / (0.03 * profile.baseline)
        for m in target.measurements
        if m.zone_id == "B" and m.metric == "flow" and m.timestamp.hour < 6
    ]
    assert max(naive_z) > 3.0


# --- H. Zone and metric independence ----------------------------------------

def test_zone_and_metric_independence(reference_measurements) -> None:
    a_only = [m for m in reference_measurements if m.zone_id == "A"]
    detector_a = AnomalyDetector(build_baseline(a_only))
    b_meas = next(m for m in reference_measurements if m.zone_id == "B")
    r = detector_a.evaluate(b_meas)
    assert r.status == STATUS_INSUFFICIENT and not r.is_anomalous

    flow_only = [m for m in reference_measurements if m.metric == "flow"]
    detector_flow = AnomalyDetector(build_baseline(flow_only))
    pressure_meas = next(
        m for m in reference_measurements if m.zone_id == "A" and m.metric == "pressure"
    )
    r = detector_flow.evaluate(pressure_meas)
    assert r.status == STATUS_INSUFFICIENT and not r.is_anomalous


# --- I. Determinism ---------------------------------------------------------

def test_determinism(reference_measurements) -> None:
    incident = _golden_incident()
    first = detect_anomalies(reference_measurements, incident.measurements)
    second = detect_anomalies(reference_measurements, incident.measurements)
    assert first == second
    assert [r.reason for r in first] == [r.reason for r in second]


# --- J. Edge cases ----------------------------------------------------------

def test_edge_insufficient_history(reference_measurements) -> None:
    target = run_simulation(build_config())
    m = target.measurements[0]  # zone A, flow, hour 0

    strict_samples = build_baseline(
        reference_measurements, BaselineConfig(minimum_samples_per_bucket=1000)
    )
    r = AnomalyDetector(strict_samples).evaluate(m)
    assert r.status == STATUS_INSUFFICIENT and r.anomaly_score is None and not r.is_anomalous

    strict_dispersion = build_baseline(
        reference_measurements, BaselineConfig(minimum_samples_for_dispersion=1000)
    )
    r = AnomalyDetector(strict_dispersion).evaluate(m)
    assert r.status == STATUS_INSUFFICIENT and r.anomaly_score is None and not r.is_anomalous


def test_edge_zero_variance(reference_measurements) -> None:
    ts = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
    constant = [Measurement(ts, "X", "flow", 100.0, "m3/h") for _ in range(10)]
    detector = AnomalyDetector(build_baseline(constant))

    same = detector.evaluate(Measurement(ts, "X", "flow", 100.0, "m3/h"))
    assert same.anomaly_score == 0.0 and same.status == STATUS_NORMAL and not same.is_anomalous

    far = detector.evaluate(Measurement(ts, "X", "flow", 105.0, "m3/h"))
    assert far.anomaly_score == 5.0 and far.is_anomalous  # dispersion floor = 1.0
    assert "{0:.1f}".format(far.anomaly_score)  # finite, interpretable


def test_edge_missing_and_invalid_values(reference_measurements) -> None:
    detector = AnomalyDetector(build_baseline(reference_measurements))
    ts = reference_measurements[0].timestamp

    nan_r = detector.evaluate(Measurement(ts, "A", "flow", float("nan"), "m3/h"))
    assert nan_r.status == STATUS_INVALID and nan_r.anomaly_score is None and not nan_r.is_anomalous

    inf_r = detector.evaluate(Measurement(ts, "A", "flow", float("inf"), "m3/h"))
    assert inf_r.status == STATUS_INVALID and not inf_r.is_anomalous

    bogus = detector.evaluate(Measurement(ts, "A", "bogus_metric", 1.0, "?"))
    assert bogus.status == STATUS_INVALID and not bogus.is_anomalous

    with pytest.raises(ValueError):
        DetectorConfig(z_threshold=0.0)
    with pytest.raises(ValueError):
        BaselineConfig(bucket_minutes=100)  # does not divide 1440


def test_edge_no_time_of_day_coverage(reference_measurements) -> None:
    # Reference only covers the first four hours of the day.
    partial = [m for m in reference_measurements if m.timestamp.hour in {0, 1, 2, 3}]
    detector = AnomalyDetector(build_baseline(partial))
    incident = _golden_incident()

    hour_10 = next(
        m for m in incident.measurements
        if m.zone_id == "B" and m.metric == "pressure" and m.timestamp.hour == 10
    )
    r = detector.evaluate(hour_10)
    assert r.status == STATUS_INSUFFICIENT and not r.is_anomalous and r.anomaly_score is None

    hour_3 = next(
        m for m in incident.measurements
        if m.zone_id == "B" and m.metric == "pressure" and m.timestamp.hour == 3
    )
    r = detector.evaluate(hour_3)
    assert r.status in {STATUS_NORMAL, STATUS_ANOMALOUS}  # covered bucket scores normally


# --- K. Integration: golden Zone B incident, seed 42 ------------------------

def test_integration_golden_zone_b_seed_42(reference_measurements) -> None:
    incident = _golden_incident()
    results = detect_anomalies(reference_measurements, incident.measurements)
    ws, we = incident.scenarios[0].window_start, incident.scenarios[0].window_end
    assert len(results) == len(incident.measurements)

    expectations = {
        "pressure": (0.9, lambda z: z < 0),
        "flow": (0.8, lambda z: z > 0),
        "consumption": (0.8, lambda z: z < 0),
        "quality": (0.5, lambda z: z < 0),
    }
    for metric, (min_fraction, direction) in expectations.items():
        rws = _in_window(results, "B", metric, ws, we)
        assert len(rws) == 24
        flagged = sum(r.is_anomalous for r in rws)
        assert flagged / len(rws) >= min_fraction, f"{metric}: only {flagged}/24 flagged"
        mean_z = sum(r.anomaly_score for r in rws) / len(rws)
        assert direction(mean_z), f"{metric}: in-window mean_z={mean_z:+.2f} wrong direction"

    in_window = [r for r in results if r.zone_id == "B" and ws <= r.timestamp < we]
    assert sum(r.is_anomalous for r in in_window) >= 60, "incident window not robustly detected"

    # Unaffected network stays quiet during the incident.
    unaffected = [r for r in results if not (r.zone_id == "B" and ws <= r.timestamp < we)]
    assert sum(r.is_anomalous for r in unaffected) / len(unaffected) < 0.02

    # The detector must never reference the scenario by name.
    assert "ZONE_B_SUPPLY_INCIDENT" not in " ".join(r.reason for r in results)