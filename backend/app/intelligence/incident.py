"""Incident generation & risk assessment (Phase 2C-B) - Incident Engine.

Transforms a Phase 2B ``CorrelatedEvidenceGroup`` into a deterministic
``IncidentAssessment`` (optionally materialising an ``Incident``) using:

- qualification     - evidence_score >= a configurable threshold
- classification   - explicit evidence rules over per-metric deviation
                      directions (never scenario names)
- risk             - the documented weighted formula:
                      risk_normalized =
                          0.30*evidence_strength
                        + 0.20*anomaly_severity
                        + 0.20*persistence
                        + 0.20*impact
                        + 0.10*citizen_context
                      risk_score = 100 * risk_normalized
- severity         - configurable bands over risk_score
- confidence       - a reliability measure DISTINCT from risk and evidence:

                      confidence =
                          0.40*evidence_strength
                        + 0.25*signal_diversity
                        + 0.15*temporal_coherence
                        + 0.20*classification_support

This module is fully deterministic. No LLM, no network, no database, no
autonomous control. All thresholds/weights are configuration (see
``IncidentConfig``) and are MVP calibration parameters, not scientific
constants.

Wording is deliberately qualified: an incident says "evidence is consistent
with a potential X event", never "a pipe has ruptured". Classification
support is an assessment-confidence input, not a statistically calibrated
probability.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.intelligence.correlation import CorrelatedEvidenceGroup
from app.simulation.models import Zone

# ---- enums ------------------------------------------------------------------


class IncidentType(str, Enum):
    WATER_LOSS = "WATER_LOSS"
    PRESSURE_ANOMALY = "PRESSURE_ANOMALY"
    WATER_QUALITY = "WATER_QUALITY"
    SUPPLY_DISRUPTION = "SUPPLY_DISRUPTION"
    UNKNOWN = "UNKNOWN"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"


class SeverityLabel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


_SEVERITY_GUIDANCE: dict[SeverityLabel, str] = {
    SeverityLabel.LOW: "monitor",
    SeverityLabel.MEDIUM: "investigate",
    SeverityLabel.HIGH: "prioritize response",
    SeverityLabel.CRITICAL: "immediate escalation",
}


# ---- configuration ----------------------------------------------------------

DEFAULT_RISK_WEIGHTS = (0.30, 0.20, 0.20, 0.20, 0.10)
DEFAULT_CONFIDENCE_WEIGHTS = (0.40, 0.25, 0.15, 0.20)
DEFAULT_SEVERITY_THRESHOLDS = (25.0, 50.0, 75.0)
DEFAULT_CITIZEN_SEVERITY_WEIGHTS = {"low": 0.4, "moderate": 0.7, "high": 1.0}
DEFAULT_CITIZEN_SEVERITY_FALLBACK = 0.6


@dataclass(frozen=True)
class IncidentConfig:
    """Knobs for the incident engine (MVP calibration parameters).

    qualification_threshold:  evidence_score >= this => candidate incident
                              (provisional; to be calibrated in 2C-B);
    risk_weights:             (evidence, severity, persistence, impact,
                              citizen) - must sum to 1.0;
    confidence_weights:       (evidence, diversity, coherence, support) -
                              must sum to 1.0;
    classification_z_threshold: mean |z| needed to consider a metric's
                              direction "significant" for classification;
    severity_full_z:          mean |z| at which the anomaly-severity factor
                              reaches 1.0;
    persistence_full_minutes: duration at which the persistence factor
                              reaches 1.0;
    impact_full_population:   population at which the impact factor reaches
                              1.0;
    impact_missing_fallback:  neutral impact factor when population is
                              missing (in [0, 1]);
    report_full_count:        citizen-report count at which the count term
                              saturates;
    citizen_severity_weights: report severity -> weight used in the citizen
                              context factor.
    """

    qualification_threshold: float = 0.50
    risk_weights: tuple[float, ...] = DEFAULT_RISK_WEIGHTS
    confidence_weights: tuple[float, ...] = DEFAULT_CONFIDENCE_WEIGHTS
    classification_z_threshold: float = 3.0
    severity_full_z: float = 12.0
    persistence_full_minutes: int = 360
    impact_full_population: int = 50_000
    impact_missing_fallback: float = 0.5
    report_full_count: int = 10
    severity_thresholds: tuple[float, ...] = DEFAULT_SEVERITY_THRESHOLDS
    citizen_severity_weights: Mapping[str, float] = field(
        default_factory=lambda: DEFAULT_CITIZEN_SEVERITY_WEIGHTS
    )
    unknown_citizen_severity_weight: float = DEFAULT_CITIZEN_SEVERITY_FALLBACK

    def __post_init__(self) -> None:
        if self.qualification_threshold <= 0:
            raise ValueError("qualification_threshold must be positive")
        if len(self.risk_weights) != 5:
            raise ValueError(f"risk_weights must have 5 entries, got {len(self.risk_weights)}")
        if any(w < 0 for w in self.risk_weights):
            raise ValueError("risk_weights must be non-negative")
        if abs(sum(self.risk_weights) - 1.0) > 1e-9:
            raise ValueError(f"risk_weights must sum to 1.0, got {sum(self.risk_weights):.4f}")
        if len(self.confidence_weights) != 4:
            raise ValueError(f"confidence_weights must have 4 entries, got {len(self.confidence_weights)}")
        if any(w < 0 for w in self.confidence_weights):
            raise ValueError("confidence_weights must be non-negative")
        if abs(sum(self.confidence_weights) - 1.0) > 1e-9:
            raise ValueError(f"confidence_weights must sum to 1.0, got {sum(self.confidence_weights):.4f}")
        if self.classification_z_threshold <= 0:
            raise ValueError("classification_z_threshold must be positive")
        if self.severity_full_z <= 0:
            raise ValueError("severity_full_z must be positive")
        if self.persistence_full_minutes <= 0:
            raise ValueError("persistence_full_minutes must be positive")
        if self.impact_full_population <= 0:
            raise ValueError("impact_full_population must be positive")
        if not (0.0 <= self.impact_missing_fallback <= 1.0):
            raise ValueError("impact_missing_fallback must be in [0, 1]")
        if self.report_full_count <= 0:
            raise ValueError("report_full_count must be positive")
        if len(self.severity_thresholds) != 3:
            raise ValueError(f"severity_thresholds must have 3 entries, got {len(self.severity_thresholds)}")
        if not (0.0 < self.severity_thresholds[0] < self.severity_thresholds[1] < self.severity_thresholds[2] < 100.0):
            raise ValueError("severity_thresholds must be strictly increasing within (0, 100)")


# ---- evidence-facing models -------------------------------------------------


@dataclass(frozen=True)
class ContributingSignal:
    """Deterministic per-metric summary of the sensor evidence."""

    metric: str
    direction: str  # "above" | "below" | "neutral"
    anomaly_count: int
    mean_z: float
    mean_abs_z: float


@dataclass(frozen=True)
class RiskFactors:
    """Five normalized risk components, each in [0, 1]."""

    evidence_strength: float
    anomaly_severity: float
    persistence: float
    impact: float
    citizen_context: float


@dataclass(frozen=True)
class Incident:
    """A materialised, actionable incident (Phase 2C output)."""

    incident_id: str
    zone_id: str
    incident_type: IncidentType
    status: IncidentStatus
    severity: SeverityLabel
    risk_score: float
    confidence: float
    start_time: datetime
    last_updated: datetime
    estimated_affected_population: int | None
    contributing_signals: tuple[ContributingSignal, ...]
    evidence: CorrelatedEvidenceGroup
    risk_factors: RiskFactors
    classification_reason: str
    explanation: str


@dataclass(frozen=True)
class IncidentAssessment:
    """Per-group result of the incident engine.

    ``qualified`` is False (and ``incident`` is None) when the correlated
    evidence does not clear the evidence threshold.
    """

    group: CorrelatedEvidenceGroup
    qualified: bool
    incident: Incident | None
    reason: str


# ---- pure helpers ------------------------------------------------------------


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def _z_sign(mean_z: float, threshold: float) -> str:
    if mean_z >= threshold:
        return "above"
    if mean_z <= -threshold:
        return "below"
    return "neutral"


# ---- classification ----------------------------------------------------------

_WATER_LOSS_SIGNATURE = {("pressure", "below"), ("flow", "above"), ("consumption", "below"), ("quality", "below")}
_SUPPLY_DISRUPTION_SIGNATURE = {
    ("consumption", "below"), ("flow", "below"), ("pressure", "below"), ("quality", "below")
}
_PRESSURE_SIGNATURE = {("pressure", "above"), ("pressure", "below")}
_WATER_QUALITY_SIGNATURE = {("quality", "above"), ("quality", "below")}


def _directions(group: CorrelatedEvidenceGroup, config: IncidentConfig) -> dict[str, str]:
    """Significant per-metric deviation direction: {"pressure": "below", ...}."""
    result: dict[str, str] = {}
    for metric in {a.metric for a in group.anomalies if _finite(a.anomaly_score) and a.metric}:
        zs = [float(a.anomaly_score) for a in group.anomalies if a.metric == metric and _finite(a.anomaly_score)]
        if not zs:
            continue
        mean_z = sum(zs) / len(zs)
        sign = _z_sign(mean_z, config.classification_z_threshold)
        if sign in ("below", "above"):
            result[metric] = sign
    return result


def classify_incident(group: CorrelatedEvidenceGroup, config: IncidentConfig) -> IncidentType:
    """Deterministic, scenario-agnostic evidence-based classification.

    Rule order (first match wins):
      1. WATER_LOSS          ::= pressure below AND flow above AND consumption below
      2. SUPPLY_DISRUPTION   ::= consumption below AND (flow below OR supply_disruption reports)
      3. PRESSURE_ANOMALY    ::= only pressure deviates significantly
      4. WATER_QUALITY       ::= only quality deviates significantly
      5. UNKNOWN             ::= anything else (ambiguous) - never forced
    """
    d = _directions(group, config)
    has_supply_reports = any(
        r.category == "supply_disruption" and r.zone_id == group.zone_id
        for r in group.citizen_reports
    )

    if d.get("pressure") == "below" and d.get("flow") == "above" and d.get("consumption") == "below":
        return IncidentType.WATER_LOSS
    if d.get("consumption") == "below" and (d.get("flow") == "below" or has_supply_reports):
        return IncidentType.SUPPLY_DISRUPTION
    if d.get("pressure") in ("above", "below") and set(d) == {"pressure"}:
        return IncidentType.PRESSURE_ANOMALY
    if d.get("quality") in ("above", "below") and set(d) == {"quality"}:
        return IncidentType.WATER_QUALITY
    return IncidentType.UNKNOWN


def classification_support(group: CorrelatedEvidenceGroup, incident_type: IncidentType) -> float:
    """Fraction of the group's anomalies consistent with the classified type.

    1.0 means every anomaly matches the type's signature; 0.0 for UNKNOWN.
    """
    if not group.anomalies:
        return 0.0
    signature: set[tuple[str, str]]
    if incident_type == IncidentType.WATER_LOSS:
        signature = _WATER_LOSS_SIGNATURE
    elif incident_type == IncidentType.SUPPLY_DISRUPTION:
        signature = _SUPPLY_DISRUPTION_SIGNATURE
    elif incident_type == IncidentType.PRESSURE_ANOMALY:
        signature = _PRESSURE_SIGNATURE
    elif incident_type == IncidentType.WATER_QUALITY:
        signature = _WATER_QUALITY_SIGNATURE
    else:
        return 0.0
    consistent = 0
    for a in group.anomalies:
        if not _finite(a.anomaly_score):
            continue
        sign = "above" if a.anomaly_score > 0 else "below"
        if (a.metric, sign) in signature:
            consistent += 1
    return consistent / len(group.anomalies)


def classification_reason(incident_type: IncidentType, directions: dict[str, str]) -> str:
    """Deterministic, human-readable reasoning for a classification."""
    if incident_type == IncidentType.WATER_LOSS:
        return (
            "Pattern pressure below + flow above + consumption below is consistent "
            "with a potential water-loss / service-loss event (physical rupture is NOT proven)."
        )
    if incident_type == IncidentType.SUPPLY_DISRUPTION:
        return (
            "Consumption below expected with reduced inflow and/or supply-disruption "
            "reports is consistent with a potential supply disruption."
        )
    if incident_type == IncidentType.PRESSURE_ANOMALY:
        return "A lone significant pressure deviation is consistent with a pressure anomaly; no other metric corroborates it."
    if incident_type == IncidentType.WATER_QUALITY:
        return "A lone significant quality deviation is consistent with a water-quality event; no other metric corroborates it."
    return "Evidence pattern is ambiguous or does not match a defined incident type; classification is UNKNOWN."


# ---- risk factors ------------------------------------------------------------

def compute_risk_factors(
    group: CorrelatedEvidenceGroup,
    population: int | None,
    config: IncidentConfig,
) -> RiskFactors:
    """Five normalized risk components, each in [0, 1]."""

    evidence_strength = _clamp01(group.evidence_score)

    zs = [abs(float(a.anomaly_score)) for a in group.anomalies if _finite(a.anomaly_score)]
    mean_abs = sum(zs) / len(zs) if zs else 0.0
    anomaly_severity = _clamp01(mean_abs / config.severity_full_z)

    persistence = _clamp01(group.persistence_minutes / config.persistence_full_minutes)

    if population is None:
        impact = _clamp01(config.impact_missing_fallback)
    else:
        impact = _clamp01(population / config.impact_full_population)

    report_count = group.citizen_report_count
    count_term = min(1.0, report_count / config.report_full_count)
    max_severity = 0.0
    for report in group.citizen_reports:
        weight = config.citizen_severity_weights.get(
            report.severity, config.unknown_citizen_severity_weight
        )
        max_severity = max(max_severity, weight)
    citizen_context = _clamp01(count_term * (0.5 + 0.5 * max_severity))

    return RiskFactors(
        evidence_strength=evidence_strength,
        anomaly_severity=anomaly_severity,
        persistence=persistence,
        impact=impact,
        citizen_context=citizen_context,
    )


def compute_risk_score(factors: RiskFactors, config: IncidentConfig) -> float:
    """risk_score = 100 * (w_e*evidence + w_s*severity + w_p*persistence + w_i*impact + w_c*citizen)."""
    w_e, w_s, w_p, w_i, w_c = config.risk_weights
    normalized = (
        w_e * factors.evidence_strength
        + w_s * factors.anomaly_severity
        + w_p * factors.persistence
        + w_i * factors.impact
        + w_c * factors.citizen_context
    )
    return round(_clamp01(normalized) * 100.0, 2)


# ---- severity ----------------------------------------------------------------

def severity_from_risk(risk_score: float, config: IncidentConfig) -> SeverityLabel:
    """Map a risk score to LOW/MEDIUM/HIGH/CRITICAL via configurable bands."""
    low, medium, high = config.severity_thresholds
    if risk_score >= high:
        return SeverityLabel.CRITICAL
    if risk_score >= medium:
        return SeverityLabel.HIGH
    if risk_score >= low:
        return SeverityLabel.MEDIUM
    return SeverityLabel.LOW


# ---- confidence --------------------------------------------------------------

def compute_confidence(
    group: CorrelatedEvidenceGroup,
    incident_type: IncidentType,
    config: IncidentConfig,
) -> float:
    """Deterministic assessment-confidence in [0, 1].

    Confidence measures how reliable/assessable the classification is. It is
    NOT a risk score and NOT a statistically calibrated failure probability.
    """
    evidence = _clamp01(group.evidence_score)
    diversity = _clamp01(group.signal_diversity)
    coherence = _clamp01(group.temporal_coherence)
    support = _clamp01(classification_support(group, incident_type))

    w_e, w_d, w_c, w_s = config.confidence_weights
    confidence = w_e * evidence + w_d * diversity + w_c * coherence + w_s * support
    return round(_clamp01(confidence), 4)


# ---- incident assembly -------------------------------------------------------


def _contributing_signals(group: CorrelatedEvidenceGroup, directions: dict[str, str]) -> tuple[ContributingSignal, ...]:
    rows: list[ContributingSignal] = []
    by_metric: dict[str, list[float]] = {}
    for a in group.anomalies:
        if a.metric and _finite(a.anomaly_score):
            by_metric.setdefault(a.metric, []).append(float(a.anomaly_score))
    for metric in sorted(by_metric):
        values = by_metric[metric]
        mean_z = sum(values) / len(values)
        mean_abs = sum(abs(v) for v in values) / len(values)
        rows.append(
            ContributingSignal(
                metric=metric,
                direction=directions.get(metric, "neutral"),
                anomaly_count=len(values),
                mean_z=round(mean_z, 3),
                mean_abs_z=round(mean_abs, 3),
            )
        )
    return tuple(rows)


def _incident_id(group: CorrelatedEvidenceGroup) -> str:
    return f"INC-{group.zone_id}-{group.start_time.strftime('%Y%m%dT%H%M%SZ')}"


def _make_incident(
    group: CorrelatedEvidenceGroup,
    incident_type: IncidentType,
    population: int | None,
    factors: RiskFactors,
    risk_score: float,
    severity: SeverityLabel,
    confidence: float,
    directions: dict[str, str],
    config: IncidentConfig,
) -> Incident:
    signals = _contributing_signals(group, directions)
    dirs = ", ".join(f"{m} {sign}" for m, sign in sorted(directions.items())) or "no significant direction"
    pattern = dirs
    explanation = (
        f"{group.summary} Classification: {incident_type.value}"
        f" (signal pattern {pattern}); {classification_reason(incident_type, directions)} "
        f"Risk factors: evidence {factors.evidence_strength:.3f}, severity "
        f"{factors.anomaly_severity:.3f}, persistence {factors.persistence:.3f}, "
        f"impact {factors.impact:.3f}, citizen {factors.citizen_context:.3f} -> "
        f"risk_score {risk_score:.2f}/100 ({severity.value}); assessment confidence "
        f"{confidence:.3f} (confidence is a reliability measure, not a probability)."
    )
    return Incident(
        incident_id=_incident_id(group),
        zone_id=group.zone_id,
        incident_type=incident_type,
        status=IncidentStatus.DETECTED,
        severity=severity,
        risk_score=risk_score,
        confidence=confidence,
        start_time=group.start_time,
        last_updated=group.end_time,
        estimated_affected_population=population,
        contributing_signals=signals,
        evidence=group,
        risk_factors=factors,
        classification_reason=classification_reason(incident_type, directions),
        explanation=explanation,
    )


# ---- engine ------------------------------------------------------------------


class IncidentAssessor:
    """Deterministic, stateless-by-config incident engine."""

    def __init__(self, config: IncidentConfig | None = None) -> None:
        self.config = config or IncidentConfig()

    def assess(
        self,
        group: CorrelatedEvidenceGroup,
        zones: Sequence[Zone] | Mapping[str, Zone] | None = None,
    ) -> IncidentAssessment:
        cfg = self.config

        score = group.evidence_score
        if not _finite(score):
            return IncidentAssessment(
                group=group,
                qualified=False,
                incident=None,
                reason="Not qualified: evidence_score is missing or not finite.",
            )

        qualified = score >= cfg.qualification_threshold
        if not qualified:
            return IncidentAssessment(
                group=group,
                qualified=False,
                incident=None,
                reason=(
                    f"Not qualified: evidence_score {score:.3f} is below threshold "
                    f"{cfg.qualification_threshold:.2f}."
                ),
            )

        population = self._population_for(group.zone_id, zones) if zones else None
        factors = compute_risk_factors(group, population, cfg)
        risk_score = compute_risk_score(factors, cfg)
        severity = severity_from_risk(risk_score, cfg)
        incident_type = classify_incident(group, cfg)
        confidence = compute_confidence(group, incident_type, cfg)
        directions = _directions(group, cfg)
        incident = _make_incident(
            group, incident_type, population, factors, risk_score, severity, confidence, directions, cfg
        )
        return IncidentAssessment(
            group=group,
            qualified=True,
            incident=incident,
            reason=(
                f"Qualified: evidence_score {score:.3f} >= threshold "
                f"{cfg.qualification_threshold:.2f}; classified {incident_type.value}."
            ),
        )

    @staticmethod
    def _population_for(zone_id: str, zones: Sequence[Zone] | Mapping[str, Zone]) -> int | None:
        by_id: Mapping[str, Zone]
        if isinstance(zones, Mapping):
            zone = zones.get(zone_id)
        else:
            by_id = {z.zone_id: z for z in zones}
            zone = by_id.get(zone_id)
        return zone.estimated_population if zone is not None else None

    def assess_many(
        self,
        groups: Sequence[CorrelatedEvidenceGroup],
        zones: Sequence[Zone] | Mapping[str, Zone] | None = None,
    ) -> tuple[IncidentAssessment, ...]:
        grouping = sorted(groups, key=lambda g: (g.start_time, g.zone_id, g.group_id))
        return tuple(self.assess(g, zones) for g in grouping)


def assess_group(
    group: CorrelatedEvidenceGroup,
    zones: Sequence[Zone] | Mapping[str, Zone] | None = None,
    config: IncidentConfig | None = None,
) -> IncidentAssessment:
    """Convenience one-shot wrapper around :class:`IncidentAssessor`."""
    return IncidentAssessor(config).assess(group, zones)


def assess_groups(
    groups: Sequence[CorrelatedEvidenceGroup],
    zones: Sequence[Zone] | Mapping[str, Zone] | None = None,
    config: IncidentConfig | None = None,
) -> tuple[IncidentAssessment, ...]:
    """Assess several groups; results are sorted deterministically."""
    return IncidentAssessor(config).assess_many(groups, zones)