import { describe, expect, it } from "vitest";
import { goldenTelemetry, normalTelemetry } from "./telemetryFixtures";

describe("telemetry deterministic fixtures", () => {
  it("golden fixture mirrors the verified B1 response shape", () => {
    expect(goldenTelemetry.run.data_source).toBe("deterministic-simulation");
    expect(goldenTelemetry.run.seed).toBe(42);
    expect(goldenTelemetry.zones).toHaveLength(4);
    expect(goldenTelemetry.scenarios).toHaveLength(1);
  });

  it("golden fixture declares the incident window from the scenario", () => {
    const scenario = goldenTelemetry.scenarios[0];
    expect(scenario.scenario_id).toBe("ZONE_B_SUPPLY_INCIDENT");
    expect(scenario.zone_id).toBe("B");
    expect(scenario.window_start).toBe("2026-01-01T06:00:00Z");
    expect(scenario.window_end).toBe("2026-01-01T12:00:00Z");
  });

  it("golden fixture exposes real levels shifting inside the window", () => {
    const bPressure = goldenTelemetry.measurements.filter(
      (m) => m.zone_id === "B" && m.metric === "pressure",
    );
    const before = bPressure.find((m) => m.timestamp === "2026-01-01T05:45:00Z");
    const inside = bPressure.find((m) => m.timestamp === "2026-01-01T06:30:00Z");
    expect(before).toBeDefined();
    expect(inside).toBeDefined();
    if (before && inside) {
      expect(inside.value).toBeLessThan(before.value);
    }
  });

  it("normal fixture has no incident window", () => {
    expect(normalTelemetry.scenarios).toEqual([]);
    expect(normalTelemetry.run.scenario).toBeNull();
  });

  it("all fixture measurements carry a unit per metric", () => {
    const units = new Set(goldenTelemetry.measurements.map((m) => m.unit));
    expect(units).toEqual(new Set(["m3/h", "bar", "mg/L"]));
  });

  it("golden fixture covers every zone and every metric", () => {
    const zonesWith = new Set(
      goldenTelemetry.measurements.map((m) => m.zone_id),
    );
    const metricsWith = new Set(
      goldenTelemetry.measurements.map((m) => m.metric),
    );
    expect(zonesWith).toEqual(new Set(["A", "B", "C", "D"]));
    expect(metricsWith).toEqual(new Set(["flow", "pressure", "quality", "consumption"]));
  });
});
