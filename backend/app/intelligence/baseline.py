"""Time-of-day baseline engine (Phase 2A - Baseline).

Builds per-zone, per-metric expected values and dispersion from a reference
(normal) measurement history, bucketed by time-of-day. The diurnal demand
pattern thereby becomes baseline behaviour rather than a source of false
anomalies. This deliberately is not a forecasting system: expected values are
simple bucket means derived from observed reference data.

Nothing here knows about incident scenarios, and nothing depends on the
database, FastAPI, or any ML/AI stack. Results are deterministic.
"""

from __future__ import annotations

import math
import statistics as st
from dataclasses import dataclass
from datetime import datetime, timezone

from app.simulation.models import Measurement


def bucket_of(dt: datetime, bucket_minutes: int) -> int:
    """Time-of-day bucket key: index within the 24 h day, aligned to UTC.

    bucket_minutes must divide 1440 evenly so buckets align to midnight.
    """
    td = dt.astimezone(timezone.utc)
    return (td.hour * 60 + td.minute) // bucket_minutes


def bucket_label(dt: datetime, bucket_minutes: int) -> str:
    start = bucket_of(dt, bucket_minutes) * bucket_minutes
    return f"{start // 60:02d}:{start % 60:02d}"


@dataclass(frozen=True)
class BaselineConfig:
    """Knobs for building a time-of-day baseline from reference data.

    bucket_minutes:            size of the time-of-day buckets.
    minimum_samples_per_bucket:minimum reference samples to emit an expected value.
    minimum_samples_for_dispersion: minimum reference samples to measure dispersion
                               (below this, scoring is refused rather than guessed).
    min_cv:                    relative dispersion floor (fraction of expected)
                               guarding against zero / near-zero variance.
    """

    bucket_minutes: int = 60
    minimum_samples_per_bucket: int = 1
    minimum_samples_for_dispersion: int = 2
    min_cv: float = 0.01

    def __post_init__(self) -> None:
        if self.bucket_minutes <= 0 or 1440 % self.bucket_minutes != 0:
            raise ValueError(
                f"bucket_minutes must divide 1440 evenly, got {self.bucket_minutes}"
            )
        if self.minimum_samples_per_bucket < 1:
            raise ValueError(
                f"minimum_samples_per_bucket must be >= 1, got {self.minimum_samples_per_bucket}"
            )
        if self.minimum_samples_for_dispersion < 2:
            raise ValueError(
                f"minimum_samples_for_dispersion must be >= 2, got {self.minimum_samples_for_dispersion}"
            )
        if not 0.0 < self.min_cv < 1.0:
            raise ValueError(f"min_cv must be in (0, 1), got {self.min_cv}")


@dataclass(frozen=True)
class BaselineSlot:
    """Statistics for one (zone, metric, time-of-day bucket)."""

    sample_count: int
    expected: float | None
    dispersion: float | None

    @property
    def is_usable(self) -> bool:
        """True when a score can be computed (expected and dispersion exist)."""
        return self.expected is not None and self.dispersion is not None


class TimeOfDayBaseline:
    """Immutable per-zone/per-metric/time-of-day reference statistics."""

    def __init__(
        self,
        slots: dict[tuple[str, str, int], BaselineSlot],
        config: BaselineConfig,
    ) -> None:
        self._slots = slots
        self._config = config

    @property
    def config(self) -> BaselineConfig:
        return self._config

    def slot(self, zone_id: str, metric: str, timestamp: datetime) -> BaselineSlot:
        """Look up the statistics for a measurement; empty slot if unseen."""
        return self._slots.get(
            (zone_id, metric, bucket_of(timestamp, self._config.bucket_minutes)),
            BaselineSlot(sample_count=0, expected=None, dispersion=None),
        )

    def expected(self, zone_id: str, metric: str, timestamp: datetime) -> float | None:
        return self.slot(zone_id, metric, timestamp).expected

    def dispersion(self, zone_id: str, metric: str, timestamp: datetime) -> float | None:
        return self.slot(zone_id, metric, timestamp).dispersion

    def label(self, timestamp: datetime) -> str:
        return bucket_label(timestamp, self._config.bucket_minutes)

    def __len__(self) -> int:
        return len(self._slots)


def build_baseline(
    measurements: list[Measurement] | tuple[Measurement, ...],
    config: BaselineConfig | None = None,
) -> TimeOfDayBaseline:
    """Build a time-of-day baseline from reference (normal) measurements.

    Non-finite reference values are ignored (they cannot inform a mean or a
    spread). Slots with fewer samples than configured are kept but marked
    unusable, so the detector can report their reason instead of a score.
    """
    cfg = config or BaselineConfig()
    groups: dict[tuple[str, str, int], list[float]] = {}
    for m in measurements:
        if not math.isfinite(m.value):
            continue
        key = (m.zone_id, m.metric, bucket_of(m.timestamp, cfg.bucket_minutes))
        groups.setdefault(key, []).append(m.value)

    slots: dict[tuple[str, str, int], BaselineSlot] = {}
    for key, vals in groups.items():
        n = len(vals)
        expected = st.fmean(vals) if n >= cfg.minimum_samples_per_bucket else None
        dispersion: float | None = None
        if expected is not None and n >= cfg.minimum_samples_for_dispersion:
            sd = st.stdev(vals) if n >= 2 else 0.0
            dispersion = max(sd, cfg.min_cv * expected)
        slots[key] = BaselineSlot(sample_count=n, expected=expected, dispersion=dispersion)

    return TimeOfDayBaseline(slots=slots, config=cfg)