"""Phase 2C-B tests: incident generation + risk assessment.

Covers the incident model, qualification (threshold + configurability),
deterministic evidence-based classification (all five types, scenario-name
independence), impact/population handling, the five risk-factor
normalizations, the exact designed risk formula, severity bands, confidence,
explainability, the golden Zone B and normal/borderline pipelines, zone
isolation, determinism, empty/malformed input, and the architectural guards
(no LLM/API, no FastAPI/database dependency).
"""

from __future__ import annotations

import math
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.intelligence import (
    STATUS_ANOMALOUS,
    AnomalyResult,
    CorrelationConfig,
    CorrelatedEvidenceGroup,
    Incident,
    IncidentAssessment,
    IncidentConfig,
    IncidentStatus,
    IncidentType,
    RiskFactors,
    SeverityLabel,
    assess_group,
    assess_groups,
    classify_incident,
    compute_confidence,
    compute_risk_factors,
    compute_risk_score,
    correlate_evidence,
    detect_anomalies,
    severity_from_risk,
)
from app.intelligence.incident import classification_support
from app.simulation import build_config, run_simulation
from app.simulation.models import CitizenReport, Measurement, Zone

REFERENCE_SEED = 99
REFERENCE_DAYS = 7.0
GOLDEN_SEED = 42

T0 = datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)

ZONES = {
    z.zone_id: z
    for z in (
        Zone("A", "Zone A", "Central", 18.5, 45_000),
        Zone("B", "Zone B", "Riverside", 12.0, 32_000),
        Zone("C", "Zone C", "North Industrial", 22.3, 18_000),
        Zone("D", "Zone D", "East Suburbs", 30.1, 52_000),
    )
}


def _minutes(offset: int) -> datetime:
    return T0 + timedelta(minutes=offset)


def _anomaly(offset: int, metric: str, z: float, zone: str = "B") -> AnomalyResult:
    return AnomalyResult(
        zone_id=zone,
        metric=metric,
        timestamp=_minutes(offset),
        observed_value=50.0,
        expected_value=55.0,
        absolute_deviation=-5.0,
        relative_deviation=-0.09,
        anomaly_score=z,
        is_anomalous=True,
        status=STATUS_ANOMALOUS,
        reason="test fixture",
    )


def _report(
    offset: int,
    zone: str = "B",
    category: str = "low_pressure",
    severity: str = "moderate",
) -> CitizenReport:
    return CitizenReport(
        report_id=f"CR-{zone}-{offset:04d}",
        zone_id=zone,
        timestamp=_minutes(offset),
        category=category,
        description=f"resident reports {category}",
        severity=severity,
        status="open",
    )


def _group(
    anomalies: list[AnomalyResult],
    reports: list[CitizenReport] | None = None,
    *,
    zone: str | None = None,
    evidence_score: float = 0.70,
    persistence_minutes: int = 0,
    temporal_coherence: float = 1.0,
) -> CorrelatedEvidenceGroup:
    anomalies = sorted(anomalies, key=lambda a: (a.timestamp, a.metric))
    reports = reports or []
    times = [a.timestamp for a in anomalies] + [r.timestamp for r in reports]
    start = min(times) if times else T0
    end = max(times) if times else T0 + timedelta(minutes=persistence_minutes)
    signal_types = tuple(sorted({a.metric for a in anomalies}))
    zone_id = zone or (anomalies[0].zone_id if anomalies else "B")
    diversity = len(signal_types) / 4.0 if signal_types else 0.0
    return CorrelatedEvidenceGroup(
        group_id=f"CGE-{zone_id}-0001",
        zone_id=zone_id,
        start_time=start,
        end_time=end + timedelta(minutes=max(0, persistence_minutes)),
        anomalies=tuple(anomalies),
        citizen_reports=tuple(sorted(reports, key=lambda r: (r.timestamp, r.report_id))),
        signal_types=signal_types,
        sensor_anomaly_count=len(anomalies),
        citizen_report_count=len(reports),
        signal_diversity=diversity,
        temporal_coherence=temporal_coherence,
        spatial_coherence=1.0,
        persistence_minutes=persistence_minutes,
        evidence_score=evidence_score,
        summary=f"zone {zone_id} evidence group (score {evidence_score:.3f})",
    )


@pytest.fixture(scope="module")
def reference_measurements() -> list[Measurement]:
    return run_simulation(
        build_config(seed=REFERENCE_SEED, duration_hours=REFERENCE_DAYS * 24.0)
    ).measurements


def _golden_correlation(reference_measurements) -> tuple:
    incident = run_simulation(
        build_config(seed=GOLDEN_SEED, scenario_ids=("ZONE_B_SUPPLY_INCIDENT",))
    )
    result = correlate_evidence(
        detect_anomalies(reference_measurements, incident.measurements), incident.reports
    )
    return result, incident


def _normal_correlation(reference_measurements) -> tuple:
    normal = run_simulation(build_config(seed=100))
    result = correlate_evidence(
        detect_anomalies(reference_measurements, normal.measurements), normal.reports
    )
    return result, normal


def _golden_incident(reference_measurements) -> Incident:
    correlation, incident = _golden_correlation(reference_measurements)
    top = max(correlation.groups, key=lambda g: g.evidence_score)
    assessment = assess_group(top, ZONES)
    assert assessment.qualified
    assert assessment.incident is not None
    return assessment.incident


# --- 1..4. model + qualification ---------------------------------------------

def test_incident_model_creation(reference_measurements) -> None:
    incident = _golden_incident(reference_measurements)
    names = {f.name for f in fields(incident)}
    for required in (
        "incident_id", "zone_id", "incident_type", "status", "severity", "risk_score",
        "confidence", "start_time", "last_updated", "estimated_affected_population",
        "contributing_signals", "evidence", "risk_factors", "classification_reason",
        "explanation",
    ):
        assert required in names, f"missing model field {required!r}"
    assert incident.status == IncidentStatus.DETECTED
    assert incident.incident_id.startswith("INC-B-")
    assert incident.zone_id == "B"
    assert 0.0 <= incident.risk_score <= 100.0
    assert 0.0 <= incident.confidence <= 1.0
    assert incident.start_time == incident.evidence.start_time
    assert incident.last_updated == incident.evidence.end_time


def test_qualification_threshold() -> None:
    weak = _group([_anomaly(0, "pressure", -8.0)], evidence_score=0.40)
    strong = _group([_anomaly(0, "pressure", -8.0)], evidence_score=0.60)
    boundary = _group([_anomaly(0, "pressure", -8.0)], evidence_score=0.50)
    assert not assess_group(weak, ZONES).qualified
    assert assess_group(strong, ZONES).qualified
    assert assess_group(boundary, ZONES).qualified  # >= threshold


def test_below_threshold_not_actionable(reference_measurements) -> None:
    correlation, normal = _normal_correlation(reference_measurements)
    top = max(correlation.groups, key=lambda g: g.evidence_score)
    assert top.evidence_score < 0.50
    assessment = assess_group(top, ZONES)
    assert not assessment.qualified
    assert assessment.incident is None
    assert "threshold" in assessment.reason


def test_threshold_is_configurable() -> None:
    group = _group([_anomaly(0, "pressure", -8.0)], evidence_score=0.60)
    assert assess_group(group, ZONES).qualified
    assert not assess_group(group, ZONES, IncidentConfig(qualification_threshold=0.70)).qualified
    assert assess_group(group, ZONES, IncidentConfig(qualification_threshold=0.30)).qualified


# --- 5..10. classification ----------------------------------------------------

def test_water_loss_classification(reference_measurements) -> None:
    assert _golden_incident(reference_measurements).incident_type == IncidentType.WATER_LOSS
    synthetic = _group(
        [
            _anomaly(0, "pressure", -8.0),
            _anomaly(0, "flow", 8.0),
            _anomaly(0, "consumption", -8.0),
        ],
        zone="B",
    )
    assert classify_incident(synthetic, IncidentConfig()) == IncidentType.WATER_LOSS


def test_pressure_anomaly_classification() -> None:
    group = _group([_anomaly(0, "pressure", -8.0)], zone="B")
    assert classify_incident(group, IncidentConfig()) == IncidentType.PRESSURE_ANOMALY
    positive = _group([_anomaly(0, "pressure", 8.0)], zone="B")
    assert classify_incident(positive, IncidentConfig()) == IncidentType.PRESSURE_ANOMALY


def test_water_quality_classification() -> None:
    group = _group([_anomaly(0, "quality", -8.0)], zone="B")
    assert classify_incident(group, IncidentConfig()) == IncidentType.WATER_QUALITY


def test_supply_disruption_classification() -> None:
    via_flow = _group(
        [_anomaly(0, "consumption", -8.0), _anomaly(0, "flow", -8.0)], zone="B"
    )
    assert classify_incident(via_flow, IncidentConfig()) == IncidentType.SUPPLY_DISRUPTION
    via_reports = _group(
        [_anomaly(0, "consumption", -8.0)],
        [_report(10, zone="B", category="supply_disruption", severity="high")],
        zone="B",
    )
    assert classify_incident(via_reports, IncidentConfig()) == IncidentType.SUPPLY_DISRUPTION


def test_unknown_for_ambiguous_evidence() -> None:
    mixed = _group([_anomaly(0, "flow", 8.0), _anomaly(0, "quality", -8.0)], zone="B")
    pressure_plus_quality = _group(
        [_anomaly(0, "pressure", -8.0), _anomaly(0, "quality", -8.0)], zone="B"
    )
    assert classify_incident(mixed, IncidentConfig()) == IncidentType.UNKNOWN
    assert classify_incident(pressure_plus_quality, IncidentConfig()) == IncidentType.UNKNOWN


def test_classification_does_not_inspect_scenario_names(reference_measurements) -> None:
    correlation, _ = _golden_correlation(reference_measurements)
    top = max(correlation.groups, key=lambda g: g.evidence_score)

    identical = _group(
        list(top.anomalies),
        list(top.citizen_reports),
        zone="B",
        evidence_score=top.evidence_score,
        persistence_minutes=top.persistence_minutes,
        temporal_coherence=top.temporal_coherence,
    )
    assert classify_incident(top, IncidentConfig()) == classify_incident(
        identical, IncidentConfig()
    ) == IncidentType.WATER_LOSS

    src = Path(__file__).parent.parent / "app" / "intelligence" / "incident.py"
    text = src.read_text(encoding="utf-8").lower()
    for token in ("scenario_ids", "zone_b_supply", "scenarios", "fixture", "pytest"):
        assert token not in text, f"incident module references forbidden token {token!r}"


# --- 11..16. factors ----------------------------------------------------------

def test_estimated_population_used() -> None:
    a = assess_group(_group([_anomaly(0, "pressure", -8.0)], zone="A"), ZONES).incident
    c = assess_group(_group([_anomaly(0, "pressure", -8.0)], zone="C"), ZONES).incident
    assert a is not None and c is not None
    assert a.estimated_affected_population == ZONES["A"].estimated_population
    assert c.estimated_affected_population == ZONES["C"].estimated_population
    assert pytest.approx(a.risk_factors.impact) == 45_000 / 50_000
    assert pytest.approx(c.risk_factors.impact) == 18_000 / 50_000
    assert a.risk_factors.impact != c.risk_factors.impact


def test_missing_population_handled_safely() -> None:
    group = _group([_anomaly(0, "pressure", -8.0)], zone="X")
    assessment = assess_group(group, zones=None)
    assert assessment.qualified
    assert assessment.incident is not None
    assert assessment.incident.estimated_affected_population is None
    assert assessment.incident.risk_factors.impact == pytest.approx(0.5)


def test_anomaly_severity_normalization() -> None:
    config = IncidentConfig()
    weak = compute_risk_factors(_group([_anomaly(0, "pressure", -3.2)]), 1, config).anomaly_severity
    medium = compute_risk_factors(_group([_anomaly(0, "pressure", -8.0)]), 1, config).anomaly_severity
    mixed = compute_risk_factors(
        _group([_anomaly(0, "pressure", -6.0), _anomaly(0, "flow", -12.0)]), 1, config
    ).anomaly_severity
    extreme = compute_risk_factors(_group([_anomaly(0, "pressure", -50.0)]), 1, config).anomaly_severity
    assert weak == pytest.approx(3.2 / 12.0)
    assert medium == pytest.approx(8.0 / 12.0)
    assert mixed == pytest.approx(9.0 / 12.0)
    assert extreme == pytest.approx(1.0)
    assert 0.0 <= weak <= medium <= mixed <= extreme <= 1.0


def test_persistence_normalization() -> None:
    config = IncidentConfig()
    zero = compute_risk_factors(_group([_anomaly(0, "pressure", -8.0)], persistence_minutes=0), 1, config).persistence
    half = compute_risk_factors(_group([_anomaly(0, "pressure", -8.0)], persistence_minutes=180), 1, config).persistence
    full = compute_risk_factors(_group([_anomaly(0, "pressure", -8.0)], persistence_minutes=500), 1, config).persistence
    assert zero == pytest.approx(0.0)
    assert half == pytest.approx(0.5)
    assert full == pytest.approx(1.0)
    assert 0.0 <= zero < half <= full


def test_citizen_context_normalization() -> None:
    config = IncidentConfig()
    none = compute_risk_factors(_group([_anomaly(0, "pressure", -8.0)]), 1, config).citizen_context
    one = compute_risk_factors(
        _group([_anomaly(0, "pressure", -8.0)], [_report(5)]), 1, config
    ).citizen_context
    five_high = compute_risk_factors(
        _group([_anomaly(0, "pressure", -8.0)], [_report(i, severity="high") for i in range(5)]), 1, config
    ).citizen_context
    twelve = compute_risk_factors(
        _group([_anomaly(0, "pressure", -8.0)], [_report(i, severity="high") for i in range(12)]), 1, config
    ).citizen_context
    assert none == pytest.approx(0.0)
    assert one == pytest.approx(0.1 * (0.5 + 0.5 * 0.7))
    assert five_high == pytest.approx(0.5)  # 5*0.1 capped count x full severity
    assert twelve == pytest.approx(1.0)  # saturated
    assert 0.0 <= none < one < five_high <= twelve <= 1.0


def test_evidence_strength_uses_phase2b_score() -> None:
    config = IncidentConfig()
    normal = compute_risk_factors(_group([_anomaly(0, "pressure", -8.0)], evidence_score=0.987), 1, config)
    clamped = compute_risk_factors(_group([_anomaly(0, "pressure", -8.0)], evidence_score=1.5), 1, config)
    assert normal.evidence_strength == pytest.approx(0.987)
    assert clamped.evidence_strength == pytest.approx(1.0)


# --- 17..19. risk formula -----------------------------------------------------

def test_risk_formula_uses_designated_weights() -> None:
    config = IncidentConfig()
    assert config.risk_weights == (0.30, 0.20, 0.20, 0.20, 0.10)
    factors = RiskFactors(0.5, 0.5, 0.5, 0.5, 0.5)
    assert compute_risk_score(factors, config) == pytest.approx(50.0)

    custom = IncidentConfig(risk_weights=(0.5, 0.2, 0.1, 0.1, 0.1))
    assert compute_risk_score(RiskFactors(1.0, 0.0, 0.0, 0.0, 0.0), custom) == pytest.approx(50.0)
    assert compute_risk_score(RiskFactors(0.0, 1.0, 0.0, 0.0, 0.0), custom) == pytest.approx(20.0)

    golden_factors = RiskFactors(0.985, 1.0, 0.958, 0.64, 1.0)
    expected = 100 * (0.30 * 0.985 + 0.20 * 1.0 + 0.20 * 0.958 + 0.20 * 0.64 + 0.10 * 1.0)
    assert compute_risk_score(golden_factors, config) == pytest.approx(expected)


def test_risk_bounded_0_to_100() -> None:
    config = IncidentConfig()
    assert compute_risk_score(RiskFactors(1, 1, 1, 1, 1), config) == pytest.approx(100.0)
    assert compute_risk_score(RiskFactors(0, 0, 0, 0, 0), config) == pytest.approx(0.0)

    weak = assess_group(_group([_anomaly(0, "pressure", -3.2)], evidence_score=0.50), ZONES)
    top = assess_group(
        _group(
            [_anomaly(0, m, z) for m, z in (("pressure", -40.0), ("flow", 40.0), ("consumption", -40.0))],
            evidence_score=1.0,
            persistence_minutes=500,
        ),
        ZONES,
    )
    assert weak.incident is not None and 0 <= weak.incident.risk_score <= 100
    assert top.incident is not None and 0 <= top.incident.risk_score <= 100
    assert weak.incident.risk_score < top.incident.risk_score


def test_weight_validation() -> None:
    with pytest.raises(ValueError):
        IncidentConfig(risk_weights=(0.2, 0.2, 0.2, 0.2, 0.1))  # sum != 1
    with pytest.raises(ValueError):
        IncidentConfig(risk_weights=(0.5, 0.5))  # wrong length
    with pytest.raises(ValueError):
        IncidentConfig(risk_weights=(-0.1, 0.3, 0.3, 0.3, 0.2))
    with pytest.raises(ValueError):
        IncidentConfig(confidence_weights=(0.5, 0.5, 0.5, -0.5))
    with pytest.raises(ValueError):
        IncidentConfig(severity_thresholds=(30, 20, 10))


# --- 20. severity -------------------------------------------------------------

def test_severity_mapping_boundaries() -> None:
    config = IncidentConfig()
    assert severity_from_risk(0, config) == SeverityLabel.LOW
    assert severity_from_risk(24, config) == SeverityLabel.LOW
    assert severity_from_risk(25, config) == SeverityLabel.MEDIUM
    assert severity_from_risk(49, config) == SeverityLabel.MEDIUM
    assert severity_from_risk(50, config) == SeverityLabel.HIGH
    assert severity_from_risk(74, config) == SeverityLabel.HIGH
    assert severity_from_risk(75, config) == SeverityLabel.CRITICAL
    assert severity_from_risk(100, config) == SeverityLabel.CRITICAL

    custom = IncidentConfig(severity_thresholds=(10, 20, 30))
    assert severity_from_risk(9, custom) == SeverityLabel.LOW
    assert severity_from_risk(10, custom) == SeverityLabel.MEDIUM
    assert severity_from_risk(30, custom) == SeverityLabel.CRITICAL


# --- 21..23. confidence -------------------------------------------------------

def test_confidence_distinct_from_risk_and_evidence(reference_measurements) -> None:
    incident = _golden_incident(reference_measurements)
    assert incident.confidence != pytest.approx(incident.risk_score / 100.0)
    assert incident.confidence != pytest.approx(incident.evidence.evidence_score)
    assert incident.confidence < 1.0


def test_confidence_increases_with_stronger_diverse_evidence(reference_measurements) -> None:
    strong = _golden_incident(reference_measurements)
    weak = assess_group(
        _group([_anomaly(0, "quality", -3.2)], evidence_score=0.60), ZONES
    ).incident
    assert weak is not None
    assert strong.confidence > weak.confidence
    assert weak.confidence > 0.6


def test_confidence_decreases_with_ambiguous_evidence() -> None:
    config = IncidentConfig()
    ambiguous = _group([_anomaly(0, "flow", 8.0), _anomaly(0, "quality", -8.0)], evidence_score=0.60)
    known_single = _group([_anomaly(0, "quality", -8.0)], evidence_score=0.60)
    assert classify_incident(ambiguous, config) == IncidentType.UNKNOWN
    assert classification_support(ambiguous, IncidentType.UNKNOWN) == 0.0
    ambiguous_conf = compute_confidence(ambiguous, IncidentType.UNKNOWN, config)
    known_conf = compute_confidence(known_single, IncidentType.WATER_QUALITY, config)
    assert ambiguous_conf < known_conf
    assert ambiguous_conf == pytest.approx(0.40 * 0.60 + 0.25 * 0.5 + 0.15 * 1.0)


# --- 24. explainability -------------------------------------------------------

def test_explainability_preserves_evidence(reference_measurements) -> None:
    incident = _golden_incident(reference_measurements)
    explanation = incident.explanation
    assert len(incident.contributing_signals) == 4
    assert {s.metric for s in incident.contributing_signals} == {
        "pressure", "flow", "consumption", "quality"
    }
    assert incident.evidence is not None
    assert "consistent with a potential water-loss" in incident.classification_reason
    assert "risk_score" in explanation
    assert "confidence" in explanation
    assert incident.zone_id in explanation
    assert f"{incident.risk_score:.2f}" in explanation
    assert all(
        hasattr(incident.risk_factors, name)
        for name in ("evidence_strength", "anomaly_severity", "persistence", "impact", "citizen_context")
    )


# --- 25..27. pipeline scenarios ----------------------------------------------

def test_golden_zone_b_full_pipeline(reference_measurements) -> None:
    correlation, incident = _golden_correlation(reference_measurements)
    assessments = assess_groups(correlation.groups, ZONES)
    qualified = [a for a in assessments if a.qualified]
    assert len(qualified) == 1  # only Zone B qualifies
    top = _golden_incident(reference_measurements)
    assert top.zone_id == "B"
    assert top.incident_type == IncidentType.WATER_LOSS
    assert set(top.evidence.signal_types) == {"pressure", "flow", "consumption", "quality"}
    assert top.evidence.sensor_anomaly_count == 89
    assert top.evidence.citizen_report_count == 12
    assert top.evidence.persistence_minutes >= 300
    assert top.evidence.evidence_score > 0.9
    assert top.risk_score >= 50.0
    assert top.severity in (SeverityLabel.HIGH, SeverityLabel.CRITICAL)
    assert top.confidence >= 0.8
    assert top.estimated_affected_population == ZONES["B"].estimated_population
    assert top.status == IncidentStatus.DETECTED


def test_normal_scenario_no_strong_incident(reference_measurements) -> None:
    correlation, normal = _normal_correlation(reference_measurements)
    assessments = assess_groups(correlation.groups, ZONES)
    assert sum(a.qualified for a in assessments) == 0
    assert normal.reports == []  # no citizen context in a healthy network


def test_zone_isolation(reference_measurements) -> None:
    correlation, _ = _golden_correlation(reference_measurements)
    assessments = assess_groups(correlation.groups, ZONES)
    for assessment in assessments:
        if assessment.qualified:
            assert assessment.incident is not None
            assert assessment.incident.zone_id == "B"
            assert assessment.incident.zone_id == assessment.group.zone_id
            assert all(a.zone_id == "B" for a in assessment.group.anomalies)

    a_inc = assess_group(_group([_anomaly(0, "pressure", -8.0)], zone="A", evidence_score=0.8), ZONES)
    b_inc = assess_group(_group([_anomaly(0, "pressure", -8.0)], zone="B", evidence_score=0.8), ZONES)
    assert a_inc.incident is not None and a_inc.incident.zone_id == "A"
    assert b_inc.incident is not None and b_inc.incident.zone_id == "B"


# --- 28..32. determinism / robustness / guards --------------------------------

def test_determinism(reference_measurements) -> None:
    correlation, incident = _golden_correlation(reference_measurements)
    first = assess_groups(correlation.groups, ZONES)
    second = assess_groups(list(reversed(correlation.groups)), ZONES)
    assert first == second
    single = assess_group(correlation.groups[-1], ZONES)
    assert assess_group(correlation.groups[-1], ZONES) == single


def test_empty_input() -> None:
    assert assess_groups([]) == ()


def test_malformed_and_missing_evidence() -> None:
    no_z = AnomalyResult(
        zone_id="B", metric="pressure", timestamp=_minutes(0), observed_value=50.0,
        expected_value=55.0, absolute_deviation=-5.0, relative_deviation=-0.09,
        anomaly_score=None, is_anomalous=True, status=STATUS_ANOMALOUS, reason="missing z",
    )
    nan_z = _anomaly(15, "pressure", float("nan"))
    no_anomalies = _group([], evidence_score=0.60)
    group = _group([no_z, nan_z], evidence_score=0.60)

    assessment = assess_group(group, ZONES)
    assert assessment.qualified  # score survives; z-gaps degrade factors safely
    assert assessment.incident is not None
    assert assessment.incident.risk_factors.anomaly_severity == pytest.approx(0.0)
    assert assessment.incident.risk_factors.citizen_context == pytest.approx(0.0)
    assert assessment.incident.incident_type == IncidentType.UNKNOWN

    empty_assessment = assess_group(no_anomalies, ZONES)
    assert empty_assessment.qualified
    assert empty_assessment.incident is not None
    assert empty_assessment.incident.incident_type == IncidentType.UNKNOWN

    bad_score = _group([_anomaly(0, "pressure", -8.0)], evidence_score=float("nan"))
    bad = assess_group(bad_score, ZONES)
    assert not bad.qualified
    assert bad.incident is None
    assert "not finite" in bad.reason


def test_no_llm_or_api_calls() -> None:
    src = Path(__file__).parent.parent / "app" / "intelligence" / "incident.py"
    text = src.read_text(encoding="utf-8")
    forbidden = (
        "import requests", "import httpx", "import urllib", "http.client",
        "aiohttp", "socket", "openai", "anthropic", "import llm", "import google",
    )
    assert all(token not in text for token in forbidden)


def test_no_fastapi_or_database_dependency() -> None:
    src = Path(__file__).parent.parent / "app" / "intelligence" / "incident.py"
    text = src.read_text(encoding="utf-8")
    for token in ("fastapi", "sqlalchemy", "app.db", "app.api", "app.main"):
        assert token not in text, f"incident module couples to {token!r}"


# --- 33. regression integration ----------------------------------------------

def test_existing_pipeline_regression(reference_measurements) -> None:
    correlation, incident = _golden_correlation(reference_measurements)
    top = max(correlation.groups, key=lambda g: g.evidence_score)
    assert top.evidence_score == pytest.approx(0.985, abs=0.01)
    assert top.sensor_anomaly_count == 89
    assert top.zone_id == "B"
    assert all(a.zone_id == "B" for a in top.anomalies)
