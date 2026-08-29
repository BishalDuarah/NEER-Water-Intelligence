import type {
  TelemetryMeasurement,
  TelemetryMetric,
  TelemetryZone,
} from "../types/telemetry";

export interface MetricMeta {
  label: string;
  unit: string;
  stroke: string;
}

export const METRIC_META: Record<TelemetryMetric, MetricMeta> = {
  flow: { label: "Flow", unit: "m³/h", stroke: "oklch(74% .14 214 / 1)" },
  pressure: { label: "Pressure", unit: "bar", stroke: "oklch(72% .16 158 / 1)" },
  quality: { label: "Quality", unit: "mg/L", stroke: "oklch(82% .15 85 / 1)" },
  consumption: {
    label: "Consumption",
    unit: "m³/h",
    stroke: "oklch(62% .21 22 / 1)",
  },
};

export function metricLabel(metric: TelemetryMetric): string {
  return METRIC_META[metric].label;
}

export function metricUnit(metric: TelemetryMetric): string {
  return METRIC_META[metric].unit;
}

export function measurementsForSeries(
  measurements: TelemetryMeasurement[],
  zoneId: string,
  metric: TelemetryMetric,
): TelemetryMeasurement[] {
  return measurements
    .filter((m) => m.zone_id === zoneId && m.metric === metric)
    .slice()
    .sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

export function zoneById(
  zones: TelemetryZone[],
  zoneId: string,
): TelemetryZone | undefined {
  return zones.find((z) => z.zone_id === zoneId);
}

export interface Point {
  x: number;
  y: number;
}

function padY(min: number, max: number): [number, number] {
  if (min === max) {
    const delta = Math.abs(min) * 0.1 || 1;
    return [min - delta, max + delta];
  }
  const range = max - min;
  return [min - range * 0.08, max + range * 0.08];
}

export interface ChartGeometry {
  innerWidth: number;
  innerHeight: number;
  xMin: number;
  xMax: number;
  yMin: number;
  yMax: number;
  points: Point[];
}

export function computeGeometry(
  measurements: TelemetryMeasurement[],
  width: number,
  height: number,
  padLeft: number,
  padRight: number,
  padTop: number,
  padBottom: number,
): ChartGeometry {
  const times = measurements.map((m) => new Date(m.timestamp).getTime());
  const values = measurements.map((m) => m.value);
  const xMin = Math.min(...times);
  const xMax = Math.max(...times);
  const [yMin, yMax] = padY(Math.min(...values), Math.max(...values));
  const innerWidth = Math.max(width - padLeft - padRight, 1);
  const innerHeight = Math.max(height - padTop - padBottom, 1);
  const points: Point[] = measurements.map((m) => {
    const x = new Date(m.timestamp).getTime();
    const t = (x - xMin) / (xMax - xMin || 1);
    const sx = padLeft + t * innerWidth;
    const sy =
      padTop +
      innerHeight -
      ((m.value - yMin) / (yMax - yMin)) * innerHeight;
    return { x: sx, y: sy };
  });
  return {
    innerWidth,
    innerHeight,
    xMin,
    xMax,
    yMin,
    yMax,
    points,
  };
}

export function toLinePath(points: Point[]): string {
  if (points.length === 0) return "";
  return points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(" ");
}

export function timeAxisTick(timestamp: string): string {
  const d = new Date(timestamp);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(
    d.getUTCMinutes(),
  ).padStart(2, "0")}Z`;
}

export function formatAxisValue(value: number): string {
  if (Math.abs(value) >= 1000) return value.toFixed(0);
  if (Math.abs(value) >= 100) return value.toFixed(1);
  return value.toFixed(2);
}
