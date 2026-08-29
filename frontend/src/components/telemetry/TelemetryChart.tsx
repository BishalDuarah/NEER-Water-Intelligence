import type { TelemetryMeasurement, TelemetryMetric } from "../../types/telemetry";
import { METRIC_META } from "../../lib/telemetry";
import {
  computeGeometry,
  formatAxisValue,
  timeAxisTick,
  toLinePath,
} from "../../lib/telemetry";

interface TelemetryChartProps {
  measurements: TelemetryMeasurement[];
  metric: TelemetryMetric;
  unit: string;
  windowStart?: string | null;
  windowEnd?: string | null;
  width?: number;
  height?: number;
  label?: string;
}

const PAD_LEFT = 48;
const PAD_RIGHT = 16;
const PAD_TOP = 12;
const PAD_BOTTOM = 22;

export function TelemetryChart({
  measurements,
  metric,
  unit,
  windowStart,
  windowEnd,
  width = 640,
  height = 220,
  label,
}: TelemetryChartProps) {
  const stroke = METRIC_META[metric].stroke;
  const series = measurements.filter((m) => m.metric === metric);
  const geometry = computeGeometry(
    series,
    width,
    height,
    PAD_LEFT,
    PAD_RIGHT,
    PAD_TOP,
    PAD_BOTTOM,
  );
  const path = toLinePath(geometry.points);
  const first = series[0];
  const last = series[series.length - 1];

  const hasWindow =
    windowStart !== null && windowStart !== undefined && series.length > 0;

  let windowRect: { x: number; w: number } | null = null;
  if (hasWindow && windowStart && windowEnd) {
    const s = new Date(windowStart).getTime();
    const e = new Date(windowEnd).getTime();
    const x1 =
      PAD_LEFT +
      ((s - geometry.xMin) / (geometry.xMax - geometry.xMin || 1)) *
        geometry.innerWidth;
    const x2 =
      PAD_LEFT +
      ((e - geometry.xMin) / (geometry.xMax - geometry.xMin || 1)) *
        geometry.innerWidth;
    windowRect = { x: x1, w: x2 - x1 };
  }

  const empty = series.length === 0;

  return (
    <figure className="telemetry-chart" data-testid="telemetry-chart">
      <figcaption className="mb-1 flex items-center justify-between gap-2">
        <span className="label-mono">{label ?? `${metric} · ${unit}`}</span>
        {hasWindow && windowRect && (
          <span className="chip border-warn/40 bg-warn/15 text-warn">
            Incident window
          </span>
        )}
      </figcaption>
      <svg
        role="img"
        aria-label={`${metric} over time in ${unit}`}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        height={height}
        data-testid="telemetry-svg"
      >
        {windowRect && (
          <rect
            x={windowRect.x}
            y={PAD_TOP}
            width={windowRect.w}
            height={geometry.innerHeight}
            className="fill-warn/10"
            stroke="oklch(82% .15 85 / 0.5)"
            strokeDasharray="3 3"
            data-testid="incident-window"
          />
        )}
        {!empty && (
          <polyline
            points={path}
            fill="none"
            stroke={stroke}
            strokeWidth={1.5}
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
            data-testid="telemetry-line"
          />
        )}
        <line
          x1={PAD_LEFT}
          y1={PAD_TOP + geometry.innerHeight}
          x2={PAD_LEFT + geometry.innerWidth}
          y2={PAD_TOP + geometry.innerHeight}
          className="stroke-border/50"
          data-testid="x-axis"
        />
        <line
          x1={PAD_LEFT}
          y1={PAD_TOP}
          x2={PAD_LEFT}
          y2={PAD_TOP + geometry.innerHeight}
          className="stroke-border/50"
        />
        {first && (
          <>
            <text
              x={PAD_LEFT}
              y={height - 6}
              className="fill-muted-foreground/70 text-[9px]"
            >
              {timeAxisTick(first.timestamp)}
            </text>
            <text
              x={PAD_LEFT + geometry.innerWidth}
              y={height - 6}
              textAnchor="end"
              className="fill-muted-foreground/70 text-[9px]"
            >
              {timeAxisTick(last.timestamp)}
            </text>
          </>
        )}
        <text
          x={4}
          y={PAD_TOP + 4}
          className="fill-muted-foreground/70 text-[9px]"
        >
          {series.length > 0 ? formatAxisValue(geometry.yMax) : ""}
        </text>
        <text
          x={4}
          y={PAD_TOP + geometry.innerHeight}
          dominantBaseline="hanging"
          className="fill-muted-foreground/70 text-[9px]"
        >
          {series.length > 0 ? formatAxisValue(geometry.yMin) : ""}
        </text>
        {series.length > 0 && (
          <text
            x={4}
            y={PAD_TOP + geometry.innerHeight / 2}
            dominantBaseline="middle"
            className="fill-muted-foreground/50 text-[9px]"
          >
            {unit}
          </text>
        )}
      </svg>
      {empty && (
        <p className="mt-1 text-xs text-muted-foreground">
          No measurements for this series.
        </p>
      )}
    </figure>
  );
}
