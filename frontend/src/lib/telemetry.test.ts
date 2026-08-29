import { describe, expect, it } from "vitest";
import {
  computeGeometry,
  formatAxisValue,
  measurementsForSeries,
  metricLabel,
  metricUnit,
  timeAxisTick,
  toLinePath,
  zoneById,
} from "./telemetry";
import { goldenTelemetry } from "../test/telemetryFixtures";

const { measurements, zones } = goldenTelemetry;

describe("metric metadata", () => {
  it("exposes the required display units", () => {
    expect(metricUnit("flow")).toBe("m³/h");
    expect(metricUnit("pressure")).toBe("bar");
    expect(metricUnit("quality")).toBe("mg/L");
    expect(metricUnit("consumption")).toBe("m³/h");
  });

  it("exposes labels for every metric", () => {
    for (const m of ["flow", "pressure", "quality", "consumption"] as const) {
      expect(metricLabel(m).length).toBeGreaterThan(0);
    }
  });
});

describe("measurementsForSeries", () => {
  it("filters to a single zone + metric and sorts by timestamp", () => {
    const series = measurementsForSeries(measurements, "B", "pressure");
    expect(series.length).toBeGreaterThan(0);
    expect(series.every((m) => m.zone_id === "B" && m.metric === "pressure")).toBe(true);
    const times = series.map((m) => m.timestamp);
    const sorted = times.slice().sort();
    expect(times).toEqual(sorted);
  });

  it("preserves the exact measurement values from the fixture", () => {
    const series = measurementsForSeries(measurements, "B", "pressure");
    expect(series.some((m) => m.value === 2.003)).toBe(true);
  });
});

describe("zoneById", () => {
  it("finds a zone by id", () => {
    expect(zoneById(zones, "B")?.name).toBe("Zone B");
    expect(zoneById(zones, "ZZ")).toBeUndefined();
  });
});

describe("computeGeometry", () => {
  const series = measurementsForSeries(measurements, "B", "pressure");
  const geometry = computeGeometry(series, 640, 220, 48, 16, 12, 22);

  it("maps the first and last points onto visible coordinates", () => {
    expect(geometry.points.length).toBe(series.length);
    const first = geometry.points[0];
    const last = geometry.points[geometry.points.length - 1];
    expect(first.x).toBe(48);
    expect(last.x).toBeCloseTo(48 + geometry.innerWidth, 1);
    expect(first.y).toBeGreaterThanOrEqual(12);
    expect(first.y).toBeLessThanOrEqual(12 + geometry.innerHeight);
  });

  it("scales the min and max values to the plot area bounds", () => {
    const ys = geometry.points.map((p) => p.y);
    expect(Math.min(...ys)).toBeGreaterThanOrEqual(12);
    expect(Math.max(...ys)).toBeLessThanOrEqual(12 + geometry.innerHeight);
  });
});

describe("chart primitives", () => {
  it("builds an SVG path from measured points only", () => {
    const points = [
      { x: 10, y: 20 },
      { x: 20, y: 30 },
    ];
    expect(toLinePath(points)).toBe("M10.00,20.00 L20.00,30.00");
    expect(toLinePath([])).toBe("");
  });

  it("formats axis tick labels and values", () => {
    expect(timeAxisTick("2026-01-01T06:15:00Z")).toBe("06:15Z");
    expect(formatAxisValue(2.003)).toBe("2.00");
    expect(formatAxisValue(3820)).toBe("3820");
  });
});
