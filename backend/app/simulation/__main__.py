"""CLI for running the water-network simulator.

Usage:
    python -m app.simulation [--seed 42] [--days 1] [--scenario ID]...
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from statistics import fmean

from app.simulation import build_config, run_simulation
from app.simulation.models import Measurement, SimulationResult
from app.simulation.scenarios import SCENARIOS

_BY_METRIC = {"flow", "pressure", "quality", "consumption"}


def _parse_iso(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"error: invalid --start-time {value!r} (expected ISO-8601)") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _unit_measurements(result: SimulationResult) -> dict[str, list[Measurement]]:
    by_metric: dict[str, list[Measurement]] = {m: [] for m in _BY_METRIC}
    for m in result.measurements:
        by_metric[m.metric].append(m)
    return by_metric


def _mean(values: list[Measurement]) -> float:
    return fmean(v.value for v in values) if values else float("nan")


def _mean_for(result: SimulationResult, zone_id: str, metric: str, window_start: datetime | None = None, window_end: datetime | None = None) -> float:
    values = [
        m
        for m in result.measurements
        if m.zone_id == zone_id
        and m.metric == metric
        and (window_start is None or m.timestamp >= window_start)
        and (window_end is None or m.timestamp < window_end)
    ]
    return _mean(values) if values else float("nan")


def _summarize(result: SimulationResult) -> str:
    cfg = result.config
    window_end = cfg.start_time + timedelta(minutes=int(cfg.duration_hours * 60))
    lines: list[str] = [
        "NEER Water Network Simulation",
        f"seed={cfg.seed} | window={_fmt(cfg.start_time)} -> {_fmt(window_end)} | interval={cfg.interval_minutes}m",
        "zones:     " + "  ".join(f"{z.zone_id} ({z.name}, pop {z.estimated_population:,})" for z in result.zones),
        "scenarios: " + (", ".join(s.scenario_id for s in result.scenarios) if result.scenarios else "none"),
        f"measurements: {len(result.measurements):,} | citizen reports: {len(result.reports)}",
        "",
        f"{'zone':<7}{'flow(m3/h)':>12}{'pressure(bar)':>14}{'quality(mg/L)':>15}{'consumption(m3/h)':>17}",
    ]
    for zone in result.zones:
        inc = any(s.zone_id == zone.zone_id for s in result.scenarios)
        lines.append(
            f"{zone.zone_id:<7}"
            f"{_mean_for(result, zone.zone_id, 'flow'):>12.1f}"
            f"{_mean_for(result, zone.zone_id, 'pressure'):>14.2f}"
            f"{_mean_for(result, zone.zone_id, 'quality'):>15.2f}"
            f"{_mean_for(result, zone.zone_id, 'consumption'):>17.1f}"
            + ("  * incident" if inc else "")
        )

    if result.scenarios:
        spec = SCENARIOS[result.scenarios[0].scenario_id]
        win_start, win_end = result.scenarios[0].window_start, result.scenarios[0].window_end
        lines.append("")
        lines.append(f"incident window effect: {spec.id} on zone {spec.zone_id} ({_fmt(win_start)} -> {_fmt(win_end)})")
        unit_by_metric = _unit_by_metric(result)
        for metric in ("pressure", "flow", "consumption", "quality"):
            inside = _mean_for(result, spec.zone_id, metric, win_start, win_end)
            outside = _mean_for(result, spec.zone_id, metric, win_end, None)
            lines.append(f"  {metric:<12} inside-window {inside:9.3f} {unit_by_metric[metric]}  vs  outside {outside:9.3f} {unit_by_metric[metric]}")

    if result.reports:
        lines.append("")
        lines.append(f"citizen reports (first {min(3, len(result.reports))} of {len(result.reports)}):")
        for r in result.reports[:3]:
            lines.append(
                f"  {r.report_id}  {_fmt(r.timestamp)}  {r.category:<18} {r.severity:<8} "
                f"{r.status:<5} {r.description}"
            )
    return "\n".join(lines)


def _unit_by_metric(result: SimulationResult) -> dict[str, str]:
    units: dict[str, str] = {}
    for m in result.measurements:
        units.setdefault(m.metric, m.unit)
    return units


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.simulation", description="Run the NEER water-network simulation (Phase 1, data generation only).")
    parser.add_argument("--seed", type=int, default=42, help="random seed for reproducible output")
    parser.add_argument("--days", type=float, default=1.0, help="simulated time window in days")
    parser.add_argument("--interval-minutes", type=int, default=15, help="measurement cadence in minutes")
    parser.add_argument("--scenario", action="append", default=[], help="scenario id(s) to apply (repeatable)")
    parser.add_argument("--start-time", default="2026-01-01T00:00:00Z", help="window start (ISO-8601, UTC)")
    parser.add_argument("--report-count", type=int, default=12, help="citizen reports per scenario")
    args = parser.parse_args()

    for sid in args.scenario:
        if sid not in SCENARIOS:
            raise SystemExit(f"error: unknown scenario {sid!r}. Known: {', '.join(sorted(SCENARIOS))}")

    config = build_config(
        seed=args.seed,
        start_time=_parse_iso(args.start_time),
        interval_minutes=args.interval_minutes,
        duration_hours=args.days * 24.0,
        scenario_ids=tuple(args.scenario),
        citizen_reports_per_scenario=args.report_count,
    )
    print(_summarize(run_simulation(config)))


if __name__ == "__main__":
    main()