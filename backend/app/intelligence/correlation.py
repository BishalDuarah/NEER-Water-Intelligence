"""Signal correlation (Phase 2B) - Correlate Engine.

Takes signal-level anomalies (Phase 2A ``AnomalyResult``) and contextual
citizen reports and groups them into correlated evidence groups.

Terminology is deliberate:
- an evidence group is NOT an incident. It only states that signals correlate
  in space and time ("correlated evidence suggests a possible common event").
  Incident generation, risk scoring and severity classification are later
  phases and are NOT here;
- the numeric strength of a group is the ``evidence_score`` (a correlation /
  coherence score), never a risk or severity score.

Design notes
------------
- Grouping is per-zone, gap-based single linkage on sorted anomaly
  timestamps. A gap larger than ``temporal_window_minutes`` starts a new
  group. Zones never merge.
- Citizen reports attach to the nearest temporally compatible group in the
  same zone AFTER clustering, so reports can never build a group by
  themselves and never dominate sensor evidence (their score share is capped
  by ``report_cap``).
- Group start/end span the actual attached evidence (anomalies + reports);
  persistence and coherence are computed from sensor anomaly timestamps only.

The evidence score (documented formula, deterministic, no LLM):
    mag  = min(sqrt(mean |z|), magnitude_cap) / magnitude_cap
    div  = min(1, #distinct signal metrics / #known metrics)
    coh  = min(1, #distinct anomaly timestamps / floor(span_min/interval) + 1)
    pers = min(1, anomaly_span_min / persistence_horizon_minutes)
    rep  = min(1, #attached reports / report_cap)
    evidence_score = w_m*mag + w_d*div + w_c*coh + w_p*pers + w_r*rep

Weights default to (0.30, 0.25, 0.15, 0.15, 0.15) and must sum to 1.0.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.intelligence.detector import STATUS_ANOMALOUS, AnomalyResult
from app.simulation.models import CitizenReport

DEFAULT_KNOWN_METRICS = ("flow", "pressure", "quality", "consumption")
DEFAULT_WEIGHTS = (0.30, 0.25, 0.15, 0.15, 0.15)  # mag, div, coh, pers, rep


def _minutes_between(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 60.0


@dataclass(frozen=True)
class CorrelationConfig:
    """Knobs for the correlation engine.

    temporal_window_minutes:      max gap between anomaly timestamps (in one
                                  zone) that keeps them in one group. 60 min =
                                  4x the 15-min cadence: tolerates a few quiet
                                  slots inside a sustained event while any
                                  unrelated same-zone activity is separated.
    report_tolerance_minutes:     how far (in minutes) a citizen report may sit
                                  outside a group before/after before attaching.
    measurement_interval_minutes: assumed sampling interval, used only to
                                  compute temporal_coherence slot counts.
    persistence_horizon_minutes:  reference duration for normalising
                                  persistence (matches the 6h incident horizon).
    report_cap:                   number of reports at which the report term
                                  saturates, keeping reports <= their weight.
    known_metrics:                metric vocabulary for signal_diversity.
    magnitude_cap:                z-magnitude ceiling (sqrt-compressed) so one
                                  extreme reading cannot dominate a group.
    evidence_weights:             (mag, div, coh, pers, rep) summing to 1.
    """

    temporal_window_minutes: int = 60
    report_tolerance_minutes: int = 60
    measurement_interval_minutes: int = 15
    persistence_horizon_minutes: int = 360
    report_cap: int = 10
    known_metrics: tuple[str, ...] = DEFAULT_KNOWN_METRICS
    magnitude_cap: float = 4.0
    evidence_weights: tuple[float, ...] = DEFAULT_WEIGHTS

    def __post_init__(self) -> None:
        for name, value in (
            ("temporal_window_minutes", self.temporal_window_minutes),
            ("report_tolerance_minutes", self.report_tolerance_minutes),
            ("measurement_interval_minutes", self.measurement_interval_minutes),
            ("persistence_horizon_minutes", self.persistence_horizon_minutes),
            ("report_cap", self.report_cap),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")
        if self.magnitude_cap <= 0:
            raise ValueError(f"magnitude_cap must be positive, got {self.magnitude_cap}")
        if not self.known_metrics:
            raise ValueError("known_metrics must not be empty")
        if len(self.evidence_weights) != 5:
            raise ValueError(f"evidence_weights must have 5 entries, got {len(self.evidence_weights)}")
        if any(w < 0 for w in self.evidence_weights):
            raise ValueError("evidence_weights must be non-negative")
        if abs(sum(self.evidence_weights) - 1.0) > 1e-9:
            raise ValueError(f"evidence_weights must sum to 1.0, got {sum(self.evidence_weights):.4f}")


@dataclass(frozen=True)
class CorrelatedEvidenceGroup:
    """A set of same-zone signal anomalies (+ citizen reports) that correlate
    in time. This is evidence of a *possible* common event, not an incident."""

    group_id: str
    zone_id: str
    start_time: datetime
    end_time: datetime
    anomalies: tuple[AnomalyResult, ...]
    citizen_reports: tuple[CitizenReport, ...]
    signal_types: tuple[str, ...]
    sensor_anomaly_count: int
    citizen_report_count: int
    signal_diversity: float
    temporal_coherence: float
    spatial_coherence: float
    persistence_minutes: int
    evidence_score: float
    summary: str


@dataclass(frozen=True)
class CorrelationResult:
    """Everything produced by one correlation pass."""

    groups: tuple[CorrelatedEvidenceGroup, ...]
    unassigned_reports: tuple[CitizenReport, ...]
    sensor_anomaly_count: int
    citizen_report_count: int
    config: CorrelationConfig


def _is_valid_anomaly(anomaly: AnomalyResult) -> bool:
    return (
        anomaly.is_anomalous
        and anomaly.status == STATUS_ANOMALOUS
        and bool(anomaly.zone_id)
        and bool(anomaly.metric)
        and anomaly.timestamp is not None
        and math.isfinite(anomaly.anomaly_score)
    )


def _cluster_anomalies(anomalies: Sequence[AnomalyResult], window_minutes: int) -> list[list[AnomalyResult]]:
    per_zone: dict[str, list[AnomalyResult]] = {}
    for anomaly in anomalies:
        per_zone.setdefault(anomaly.zone_id, []).append(anomaly)

    clusters: list[list[AnomalyResult]] = []
    for zone_anomalies in per_zone.values():
        ordered = sorted(zone_anomalies, key=lambda a: (a.timestamp, a.metric))
        current: list[AnomalyResult] = []
        for anomaly in ordered:
            if current and _minutes_between(current[-1].timestamp, anomaly.timestamp) > window_minutes:
                clusters.append(current)
                current = []
            current.append(anomaly)
        if current:
            clusters.append(current)
    return clusters


def _sorted_anomalies(anomalies: Sequence[AnomalyResult]) -> tuple[AnomalyResult, ...]:
    return tuple(sorted(anomalies, key=lambda a: (a.timestamp, a.metric, a.zone_id)))


def _sorted_reports(reports: Sequence[CitizenReport]) -> tuple[CitizenReport, ...]:
    return tuple(sorted(reports, key=lambda r: (r.timestamp, r.report_id)))


def _attach_reports(
    clusters: Sequence[Sequence[AnomalyResult]],
    reports: Sequence[CitizenReport],
    tolerance_minutes: int,
) -> tuple[dict[int, list[CitizenReport]], list[CitizenReport]]:
    """Attach each report to the nearest compatible same-zone group.

    A report fits if its timestamp lies within [start - tol, end + tol] of a
    group (spans measured from anomaly evidence only, before reports extend
    them). Reports that fit no group stay unassigned and never form groups.
    """
    spans: list[tuple[datetime, datetime]] = []
    for cluster in clusters:
        times = [a.timestamp for a in cluster]
        spans.append((min(times), max(times)))

    assigned: dict[int, list[CitizenReport]] = {i: [] for i in range(len(clusters))}
    unassigned: list[CitizenReport] = []
    for report in _sorted_reports(reports):
        if not report.zone_id:
            unassigned.append(report)
            continue
        candidates: list[tuple[float, int, datetime]] = []
        for idx, (start, end) in enumerate(spans):
            if report.zone_id != clusters[idx][0].zone_id:
                continue
            low = start - timedelta(minutes=tolerance_minutes)
            high = end + timedelta(minutes=tolerance_minutes)
            if low <= report.timestamp <= high:
                midpoint = start + (end - start) / 2
                distance = abs(report.timestamp - midpoint)
                candidates.append((distance, idx, start))
        if not candidates:
            unassigned.append(report)
            continue
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        assigned[candidates[0][1]].append(report)
    return assigned, unassigned


def _evidence_score(
    anomalies: Sequence[AnomalyResult],
    report_count: int,
    config: CorrelationConfig,
) -> tuple[float, float, float, float, int]:
    """Return (evidence_score, signal_diversity, temporal_coherence, persistence_component, persistence_minutes)."""
    first = min(a.timestamp for a in anomalies)
    last = max(a.timestamp for a in anomalies)
    persistence_minutes = int(_minutes_between(first, last))
    span_min = max(0.0, _minutes_between(first, last))

    magnitude = min(math.sqrt(sum(abs(a.anomaly_score) for a in anomalies) / len(anomalies)), config.magnitude_cap)
    magnitude_normalised = magnitude / config.magnitude_cap

    signal_types = {a.metric for a in anomalies}
    diversity = min(1.0, len(signal_types) / max(1, len(config.known_metrics)))

    distinct_timestamps = len({a.timestamp for a in anomalies})
    expected_slots = int(span_min // config.measurement_interval_minutes) + 1
    coherence = min(1.0, distinct_timestamps / max(1, expected_slots))

    persistence = min(1.0, span_min / config.persistence_horizon_minutes)
    reports = min(1.0, report_count / config.report_cap)

    w_m, w_d, w_c, w_p, w_r = config.evidence_weights
    score = (
        w_m * magnitude_normalised
        + w_d * diversity
        + w_c * coherence
        + w_p * persistence
        + w_r * reports
    )
    return score, diversity, coherence, persistence, persistence_minutes


def _build_group(
    anomalies: Sequence[AnomalyResult],
    reports: Sequence[CitizenReport],
    config: CorrelationConfig,
) -> CorrelatedEvidenceGroup:
    anomaly_tuple = _sorted_anomalies(anomalies)
    report_tuple = _sorted_reports(reports)
    times = [a.timestamp for a in anomaly_tuple]
    evidence_times = times + [r.timestamp for r in report_tuple]
    start_time = min(evidence_times)
    end_time = max(evidence_times)

    signal_types = tuple(sorted({a.metric for a in anomaly_tuple}))
    score, diversity, coherence, _, persistence_minutes = _evidence_score(
        anomaly_tuple, len(report_tuple), config
    )

    zone_id = anomaly_tuple[0].zone_id
    summary = (
        f"zone {zone_id}: {len(signal_types)} signal type(s) "
        f"({', '.join(signal_types)}), {len(anomaly_tuple)} sensor anomalies over "
        f"{persistence_minutes} min, {len(report_tuple)} citizen report(s); correlated "
        f"evidence suggesting a possible common event (coherence {coherence:.2f}, "
        f"evidence score {score:.3f})."
    )

    return CorrelatedEvidenceGroup(
        group_id="",
        zone_id=zone_id,
        start_time=start_time,
        end_time=end_time,
        anomalies=anomaly_tuple,
        citizen_reports=report_tuple,
        signal_types=signal_types,
        sensor_anomaly_count=len(anomaly_tuple),
        citizen_report_count=len(report_tuple),
        signal_diversity=diversity,
        temporal_coherence=coherence,
        spatial_coherence=1.0,
        persistence_minutes=persistence_minutes,
        evidence_score=score,
        summary=summary,
    )


class CorrelateEngine:
    """Deterministic, stateless-by-config correlation engine."""

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self.config = config or CorrelationConfig()

    def correlate(
        self,
        anomalies: Sequence[AnomalyResult],
        citizen_reports: Sequence[CitizenReport] | None = None,
    ) -> CorrelationResult:
        valid = [a for a in anomalies if _is_valid_anomaly(a)]
        reports = list(citizen_reports) if citizen_reports else []

        clusters = _cluster_anomalies(valid, self.config.temporal_window_minutes)
        assigned, unassigned = _attach_reports(
            clusters, reports, self.config.report_tolerance_minutes
        )

        unordered: list[CorrelatedEvidenceGroup] = []
        for idx, cluster in enumerate(clusters):
            unordered.append(_build_group(cluster, assigned[idx], self.config))

        ordered = sorted(unordered, key=lambda g: (g.start_time, g.zone_id))
        groups = tuple(
            dataclasses.replace(g, group_id=f"CGE-{g.zone_id}-{idx:04d}")
            for idx, g in enumerate(ordered, start=1)
        )
        del unordered
        return CorrelationResult(
            groups=groups,
            unassigned_reports=_sorted_reports(unassigned),
            sensor_anomaly_count=len(valid),
            citizen_report_count=len(reports),
            config=self.config,
        )


def correlate_evidence(
    anomalies: Sequence[AnomalyResult],
    citizen_reports: Sequence[CitizenReport] | None = None,
    config: CorrelationConfig | None = None,
) -> CorrelationResult:
    """Convenience one-shot wrapper around :class:`CorrelateEngine`."""
    return CorrelateEngine(config).correlate(anomalies, citizen_reports)