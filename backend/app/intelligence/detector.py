"""Signal-level anomaly detection (Phase 2A - Anomaly Detection).

Evaluates each measurement against a time-of-day baseline and produces an
interpretable z-score (anomaly_score) plus a binary signal-level finding
(is_anomalous). This is detection only:

- it does NOT know about incident scenarios (it only sees measurements and a
  reference baseline),
- it does NOT create incidents,
- it does NOT compute risk scores.

An anomaly here means: this one measurement deviates unusually far from what
its zone+metric expects at that time of day. Correlating these findings into an
incident is a later phase.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.intelligence.baseline import BaselineConfig, TimeOfDayBaseline, build_baseline
from app.simulation.models import Measurement

STATUS_NORMAL = "normal"
STATUS_ANOMALOUS = "anomalous"
STATUS_INSUFFICIENT = "insufficient_baseline"
STATUS_INVALID = "invalid_measurement"


@dataclass(frozen=True)
class DetectorConfig:
    """Knobs for anomaly evaluation.

    z_threshold: absolute z-score above which a measurement is anomalous.
                 The canonical 3-sigma rule; ~0.3% of healthy Gaussian noise
                 exceeds it per measurement by design.
    metrics:     the metrics the detector understands; anything else is
                 reported as invalid rather than silently scored.
    """

    z_threshold: float = 3.0
    metrics: tuple[str, ...] = ("flow", "pressure", "quality", "consumption")

    def __post_init__(self) -> None:
        if self.z_threshold <= 0:
            raise ValueError(f"z_threshold must be positive, got {self.z_threshold}")
        if not self.metrics:
            raise ValueError("metrics must not be empty")


@dataclass(frozen=True)
class AnomalyResult:
    """Signal-level finding for a single measurement."""

    zone_id: str
    metric: str
    timestamp: datetime
    observed_value: float
    expected_value: float | None
    absolute_deviation: float | None
    relative_deviation: float | None
    anomaly_score: float | None
    is_anomalous: bool
    status: str
    reason: str


class AnomalyDetector:
    """Evaluates measurements against a previously built baseline."""

    def __init__(
        self,
        baseline: TimeOfDayBaseline,
        config: DetectorConfig | None = None,
    ) -> None:
        self._baseline = baseline
        self._config = config or DetectorConfig()

    def evaluate(self, m: Measurement) -> AnomalyResult:
        """Score one measurement; never raises for data-level problems."""
        if m.metric not in self._config.metrics:
            return AnomalyResult(
                zone_id=m.zone_id, metric=m.metric, timestamp=m.timestamp,
                observed_value=m.value, expected_value=None, absolute_deviation=None,
                relative_deviation=None, anomaly_score=None, is_anomalous=False,
                status=STATUS_INVALID, reason=f"unsupported metric {m.metric!r}",
            )
        if not math.isfinite(m.value):
            return AnomalyResult(
                zone_id=m.zone_id, metric=m.metric, timestamp=m.timestamp,
                observed_value=m.value, expected_value=None, absolute_deviation=None,
                relative_deviation=None, anomaly_score=None, is_anomalous=False,
                status=STATUS_INVALID, reason="observed value is not finite",
            )

        slot = self._baseline.slot(m.zone_id, m.metric, m.timestamp)
        need_p = self._baseline.config.minimum_samples_per_bucket
        need_d = self._baseline.config.minimum_samples_for_dispersion
        where = f"zone {m.zone_id} metric {m.metric} at {self._baseline.label(m.timestamp)} UTC"

        if slot.sample_count == 0:
            return self._insufficient(m, f"no reference samples for {where}")
        if slot.expected is None:
            return self._insufficient(
                m, f"only {slot.sample_count} reference sample(s) for {where}; need >= {need_p}"
            )
        if slot.dispersion is None:
            return self._insufficient(
                m, f"sample count {slot.sample_count} < {need_d} for dispersion of {where}"
            )

        expected = slot.expected
        dev = m.value - expected
        relative = dev / expected if expected != 0.0 else None
        z = dev / slot.dispersion
        anomalous = abs(z) > self._config.z_threshold

        if anomalous:
            direction = "above" if z > 0.0 else "below"
            pct = f"{relative * 100.0:+.1f}%" if relative is not None else "n/a"
            reason = (
                f"{m.metric} {m.value:.3f} {m.unit} {direction} expected "
                f"{expected:.3f} {m.unit} by {pct} (|z|={abs(z):.2f} > "
                f"{self._config.z_threshold})"
            )
            status = STATUS_ANOMALOUS
        else:
            reason = (
                f"{m.metric} within expected range (z={z:+.2f}, "
                f"threshold {self._config.z_threshold})"
            )
            status = STATUS_NORMAL

        return AnomalyResult(
            zone_id=m.zone_id,
            metric=m.metric,
            timestamp=m.timestamp,
            observed_value=m.value,
            expected_value=expected,
            absolute_deviation=dev,
            relative_deviation=relative,
            anomaly_score=z,
            is_anomalous=anomalous,
            status=status,
            reason=reason,
        )

    def evaluate_many(self, measurements: Sequence[Measurement]) -> list[AnomalyResult]:
        return [self.evaluate(m) for m in measurements]

    def _insufficient(self, m: Measurement, reason: str) -> AnomalyResult:
        return AnomalyResult(
            zone_id=m.zone_id, metric=m.metric, timestamp=m.timestamp,
            observed_value=m.value, expected_value=None, absolute_deviation=None,
            relative_deviation=None, anomaly_score=None, is_anomalous=False,
            status=STATUS_INSUFFICIENT, reason=reason,
        )


def detect_anomalies(
    reference_measurements: Sequence[Measurement],
    target_measurements: Sequence[Measurement],
    baseline_config: BaselineConfig | None = None,
    detector_config: DetectorConfig | None = None,
) -> list[AnomalyResult]:
    """Build a time-of-day baseline from reference data and score the target.

    The reference is ordinary (non-incident) data; the target is the data to
    evaluate. Both must already exist - this function performs no simulation.
    """
    baseline = build_baseline(list(reference_measurements), baseline_config)
    return AnomalyDetector(baseline, detector_config).evaluate_many(target_measurements)