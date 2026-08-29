import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TelemetryChart } from "./TelemetryChart";
import { goldenTelemetry, normalTelemetry } from "../../test/telemetryFixtures";
import { measurementsForSeries } from "../../lib/telemetry";

describe("TelemetryChart", () => {
  it("renders a polyline computed from the measured values only", () => {
    const measurements = measurementsForSeries(
      goldenTelemetry.measurements,
      "B",
      "pressure",
    );
    const { container } = render(
      <TelemetryChart
        measurements={measurements}
        metric="pressure"
        unit="bar"
        label="Test"
      />,
    );

    expect(screen.getByTestId("telemetry-chart")).not.toBeNull();
    const line = screen.getByTestId("telemetry-line");
    expect(line.getAttribute("points")).toBeTruthy();
    expect(screen.getByText("bar")).not.toBeNull();
    expect(container.querySelectorAll("polyline").length).toBeGreaterThan(0);
  });

  it("marks the incident window from the scenario, not inferred", () => {
    const measurements = goldenTelemetry.measurements;
    const scenario = goldenTelemetry.scenarios[0];
    render(
      <TelemetryChart
        measurements={measurements}
        metric="pressure"
        unit="bar"
        windowStart={scenario.window_start}
        windowEnd={scenario.window_end}
        label="Zone B"
      />,
    );

    expect(screen.getByTestId("incident-window")).not.toBeNull();
    expect(screen.getByText("Incident window")).not.toBeNull();
  });

  it("shows no incident window when no scenario is provided", () => {
    render(
      <TelemetryChart
        measurements={measurementsForSeries(
          normalTelemetry.measurements,
          "B",
          "pressure",
        )}
        metric="pressure"
        unit="bar"
        label="Zone B"
      />,
    );

    expect(screen.queryByTestId("incident-window")).toBeNull();
  });

  it("renders an empty-state message when there are no measurements", () => {
    render(
      <TelemetryChart measurements={[]} metric="flow" unit="m³/h" label="Empty" />,
    );
    expect(
      screen.getByText("No measurements for this series."),
    ).not.toBeNull();
  });
});
