"""Phase 2B tests: signal correlation engine.

Covers grouping, zone isolation, temporal windows, signal diversity,
persistence, citizen-report correlation/preservation/non-dominance, quiet
normal runs, the golden Zone B scenario, determinism, empty/invalid inputs,
multiple independent groups, and the architectural guards (no network/LLM,
no incident objects, no risk/severity fields).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.intelligence import (
    STATUS_ANOMALOUS,
    STATUS_INSUFFICIENT,
    STATUS_NORMAL,
    AnomalyResult,
    CorrelationConfig,
    CorrelatedEvidenceGroup,
    CorrelationResult,
    correlate_evidence,
    detect_anomalies,
)
from app.simulation import build_config, run_simulation
from app.simulation.models import CitizenReport, Measurement

REFERENCE_SEED = 99
REFERENCE_DAYS = 7.0
GOLDEN_SEED = 42

T0 = datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)


def _minutes(offset: int) -> datetime:
    return T0 + timedelta(minutes=offset)


def _anom(
    offset: int,
    zone: str = "B",
    metric: str = "pressure",
    z: float = -3.2,
    status: str = STATUS_ANOMALOUS,
) -> AnomalyResult:
    return AnomalyResult(
        zone_id=zone,
        metric=metric,
        timestamp=_minutes(offset),
        observed_value=50.0,
        expected_value=55.0,
        absolute_deviation=-5.0,
        relative_deviation=-0.09,
        anomaly_score=z,
        is_anomalous=status == STATUS_ANOMALOUS,
        status=status,
        reason="test fixture",
    )


def _report(
    offset: int,
    zone: str = "B",
    category: str = "low_pressure",
    severity: str = "moderate",
    report_id: str | None = None,
) -> CitizenReport:
    return CitizenReport(
        report_id=report_id or f"CR-{zone}-{offset:04d}",
        zone_id=zone,
        timestamp=_minutes(offset),
        category=category,
        description=f"resident reports {category}",
        severity=severity,
        status="open",
    )


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


def _normal_run():
    return run_simulation(build_config(seed=100))


# --- 1. Grouping -------------------------------------------------------------

def test_same_zone_anomalies_correlate_into_one_group() -> None:
    result = correlate_evidence(
        [_anom(0, zone="B", metric="pressure"), _anom(0, zone="B", metric="flow")]
    )
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.zone_id == "B"
    assert group.sensor_anomaly_count == 2
    assert group.signal_types == ("flow", "pressure")


def test_different_zones_never_merge() -> None:
    result = correlate_evidence(
        [_anom(0, zone="A"), _anom(0, zone="B")]
    )
    assert len(result.groups) == 2
    assert {g.zone_id for g in result.groups} == {"A", "B"}
    for group in result.groups:
        assert all(a.zone_id == group.zone_id for a in group.anomalies)
        assert all(r.zone_id == group.zone_id for r in group.citizen_reports)


def test_nearby_timestamps_correlate() -> None:
    result = correlate_evidence(
        [_anom(0, zone="A"), _anom(15, zone="A")]
    )
    assert len(result.groups) == 1


def test_distant_timestamps_do_not_correlate() -> None:
    result = correlate_evidence(
        [_anom(0, zone="A"), _anom(180, zone="A")]
    )
    assert len(result.groups) == 2


# --- 2. Signal diversity -----------------------------------------------------

def test_signal_diversity_increases_with_metric_types() -> None:
    single = correlate_evidence([_anom(0, zone="A", metric="pressure")]).groups[0]
    multi = correlate_evidence(
        [_anom(0, zone="A", metric="pressure"), _anom(0, zone="A", metric="flow")]
    ).groups[0]
    assert single.signal_types == ("pressure",)
    assert multi.signal_types == ("flow", "pressure")
    assert single.signal_diversity == pytest.approx(0.25)
    assert multi.signal_diversity == pytest.approx(0.5)
    assert multi.evidence_score > single.evidence_score


def test_repeated_same_metric_does_not_inflate_diversity() -> None:
    anomalies = [_anom(i * 15, zone="A", metric="pressure") for i in range(6)]
    result = correlate_evidence(anomalies)
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.signal_types == ("pressure",)
    assert group.sensor_anomaly_count == 6
    assert group.signal_diversity == pytest.approx(0.25)


# --- 3. Magnitude / persistence ---------------------------------------------

def test_stronger_z_score_produces_stronger_evidence() -> None:
    weak = correlate_evidence([_anom(0, zone="A", z=-3.2)]).groups[0]
    strong = correlate_evidence([_anom(0, zone="A", z=-8.0)]).groups[0]
    assert strong.evidence_score > weak.evidence_score


def test_persistent_group_scores_above_isolated() -> None:
    config = CorrelationConfig(temporal_window_minutes=90)
    isolated = correlate_evidence([_anom(0, zone="A", z=-3.2)]).groups[0]
    persistent = correlate_evidence(
        [_anom(i * 15, zone="A", z=-3.2) for i in range(6)], config=config
    ).groups[0]
    assert persistent.sensor_anomaly_count == 6
    assert persistent.persistence_minutes >= 75
    assert persistent.evidence_score > isolated.evidence_score


# --- 4. Citizen reports ------------------------------------------------------

def test_report_correlates_by_zone_and_time() -> None:
    result = correlate_evidence(
        [_anom(0, zone="B")],
        [_report(20, zone="B"), _report(20, zone="A"), _report(150, zone="B")],
    )
    group = result.groups[0]
    assert group.citizen_report_count == 1
    assert group.citizen_reports[0].zone_id == "B"
    assert len(result.unassigned_reports) == 2
    assert {r.zone_id for r in result.unassigned_reports} == {"A", "B"}


def test_report_fields_are_preserved_on_group() -> None:
    report = _report(20, zone="B", category="supply_disruption", severity="high")
    group = correlate_evidence([_anom(0, zone="B")], [report]).groups[0]
    attached = group.citizen_reports[0]
    assert attached.report_id == report.report_id
    assert attached.category == "supply_disruption"
    assert attached.description == report.description
    assert attached.severity == "high"
    assert attached.status == "open"


def test_citizen_reports_do_not_dominate_evidence() -> None:
    anomaly = _anom(0, zone="B", z=-3.2)
    base = correlate_evidence([anomaly]).groups[0]
    with_reports = correlate_evidence([anomaly], [_report(offset) for offset in (5, 20, 40, 60, 80)]).groups[0]
    many = correlate_evidence([anomaly], [_report(offset) for offset in range(5, 500, 5)]).groups[0]

    delta = with_reports.evidence_score - base.evidence_score
    assert 0.0 < delta <= 0.15 + 1e-9
    rep_boost = many.evidence_score - base.evidence_score
    assert rep_boost == pytest.approx(0.15)  # capped at report weight despite 99 reports

    corroborated = correlate_evidence(
        [_anom(0, zone="B", metric="flow", z=-8.0),
         _anom(0, zone="B", metric="pressure", z=-8.0),
         _anom(0, zone="B", metric="quality", z=-8.0),
         _anom(0, zone="B", metric="consumption", z=-8.0)],
    ).groups[0]
    assert corroborated.evidence_score > many.evidence_score


# --- 5. Quiet normal run / golden incident -----------------------------------

def test_normal_simulation_has_no_strong_event(reference_measurements) -> None:
    normal = _normal_run()
    anomalies = detect_anomalies(reference_measurements, normal.measurements)
    result = correlate_evidence(anomalies, normal.reports)
    assert len(result.groups) >= 1
    assert all(len(g.signal_types) <= 2 for g in result.groups)
    max_score = max(g.evidence_score for g in result.groups)
    assert max_score < 0.5, f"normal run produced strong evidence {max_score:.3f}"


def test_golden_zone_b_produces_strong_coherent_group(reference_measurements) -> None:
    incident = _golden_incident()
    anomalies = detect_anomalies(reference_measurements, incident.measurements)
    result = correlate_evidence(anomalies, incident.reports)

    top = max(result.groups, key=lambda g: g.evidence_score)
    assert top.zone_id == "B"
    assert set(top.signal_types) == {"pressure", "flow", "consumption", "quality"}
    assert top.signal_diversity == pytest.approx(1.0)
    assert top.citizen_report_count == len(incident.reports) == 12
    assert top.sensor_anomaly_count >= 80
    assert top.persistence_minutes >= 300
    assert top.temporal_coherence >= 0.8
    assert top.evidence_score >= 0.8
    assert "suggesting a possible common event" in top.summary


def test_other_zones_stay_isolated_in_golden(reference_measurements) -> None:
    incident = _golden_incident()
    anomalies = detect_anomalies(reference_measurements, incident.measurements)
    result = correlate_evidence(anomalies, incident.reports)

    foreign = [g for g in result.groups if g.zone_id != "B"]
    assert foreign, "golden run should still produce weak isolated groups elsewhere"
    assert all(len(g.signal_types) <= 2 for g in foreign)
    assert max(g.evidence_score for g in foreign) < 0.6

    for group in result.groups:
        if group.zone_id == "B":
            assert all(a.zone_id == "B" for a in group.anomalies)
            assert all(r.zone_id == "B" for r in group.citizen_reports)


# --- 6. Determinism / robustness ---------------------------------------------

def test_deterministic_across_repeated_and_shuffled_input(reference_measurements) -> None:
    incident = _golden_incident()
    anomalies = detect_anomalies(reference_measurements, incident.measurements)

    first = correlate_evidence(anomalies, incident.reports)
    second = correlate_evidence(anomalies, incident.reports)
    third = correlate_evidence(list(reversed(anomalies)), list(reversed(incident.reports)))
    assert first == second == third


def test_empty_inputs_are_safe() -> None:
    result = correlate_evidence([])
    assert isinstance(result, CorrelationResult)
    assert result.groups == ()
    assert result.unassigned_reports == ()
    assert result.sensor_anomaly_count == 0
    assert result.citizen_report_count == 0


def test_empty_reports_still_group_anomalies() -> None:
    result = correlate_evidence([_anom(0, zone="A"), _anom(15, zone="A")])
    assert len(result.groups) == 1
    assert result.groups[0].citizen_report_count == 0
    assert result.unassigned_reports == ()


def test_invalid_and_non_finite_data_excluded() -> None:
    valid = _anom(0, zone="A", z=-5.0)
    nan = _anom(15, zone="A", z=float("nan"))
    inf = _anom(30, zone="A", z=float("inf"))
    not_anom = _anom(45, zone="A", z=-4.0, status=STATUS_NORMAL)
    insufficient = _anom(60, zone="A", z=-4.0, status=STATUS_INSUFFICIENT)
    blank_zone = _anom(75, zone="")

    result = correlate_evidence(
        [valid, nan, inf, not_anom, insufficient, blank_zone],
        [_report(5, zone="A"), _report(10, zone="")],
    )
    assert result.sensor_anomaly_count == 1
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.anomalies == (valid,)
    assert group.citizen_report_count == 1
    assert [r.zone_id for r in result.unassigned_reports] == [""]


def test_multiple_independent_events_form_multiple_groups() -> None:
    anomalies = [
        _anom(0, zone="B", metric="pressure"),
        _anom(15, zone="B", metric="flow"),
        _anom(30, zone="B", metric="quality"),
        _anom(240, zone="B", metric="pressure"),
        _anom(500, zone="A", metric="pressure"),
    ]
    result = correlate_evidence(anomalies)
    assert len(result.groups) == 3
    b1, b2, a = result.groups  # sorted by start_time
    assert (b1.zone_id, b2.zone_id, a.zone_id) == ("B", "B", "A")
    assert b1.sensor_anomaly_count == 3
    assert b2.sensor_anomaly_count == 1
    assert a.sensor_anomaly_count == 1
    assert len({g.group_id for g in result.groups}) == 3
    assert all(g.group_id.startswith("CGE-") for g in result.groups)


# --- 7. Architectural guards -------------------------------------------------

def test_correlation_uses_no_network_or_llm_imports() -> None:
    import app.intelligence.correlation
    import app.intelligence.detector

    source = Path(app.intelligence.correlation.__file__).read_text(encoding="utf-8")
    source += Path(app.intelligence.detector.__file__).read_text(encoding="utf-8")
    forbidden = (
        "import requests", "import httpx", "import urllib", "http.client",
        "aiohttp", "socket", "openai", "anthropic", "import llm",
    )
    assert all(token not in source for token in forbidden)


def test_evidence_groups_are_not_incident_objects() -> None:
    group = correlate_evidence([_anom(0, zone="A")]).groups[0]
    assert isinstance(group, CorrelatedEvidenceGroup)
    assert not hasattr(group, "incident_id")
    assert not hasattr(group, "incident_status")
    assert all(not hasattr(g, "incident_id") for g in correlate_evidence([_anom(15, zone="A")]).groups)


def test_no_risk_or_severity_fields() -> None:
    group = correlate_evidence([_anom(0, zone="A")]).groups[0]
    for name in ("risk_score", "risk_level", "severity", "severity_level"):
        assert not hasattr(group, name), f"evidence group leaked {name!r}"
    result = correlate_evidence([_anom(0, zone="A")])
    for name in ("risk_score", "risk_level", "severity"):
        assert not hasattr(result, name)