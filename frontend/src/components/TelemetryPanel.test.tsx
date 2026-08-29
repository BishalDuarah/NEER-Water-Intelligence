import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TelemetryPanel } from "./TelemetryPanel";
import { goldenTelemetry, normalTelemetry } from "../test/telemetryFixtures";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TelemetryPanel", () => {
  it("is idle until the operator loads telemetry", () => {
    render(<TelemetryPanel />);
    expect(
      screen.getByRole("button", { name: /Load telemetry/ }),
    ).not.toBeNull();
    expect(screen.queryByTestId("telemetry-chart")).toBeNull();
  });

  it("loads telemetry on demand and renders a real chart from measurements", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(<TelemetryPanel />);

    fireEvent.click(screen.getByRole("button", { name: /Load telemetry/ }));

    expect(
      await screen.findByTestId("telemetry-chart"),
    ).not.toBeNull();
    expect(screen.getByTestId("telemetry-line")).not.toBeNull();
    expect(screen.getByText("Rerun telemetry")).not.toBeNull();
  });

  it("surfaces incident windows when the scenario is loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(<TelemetryPanel scenario="ZONE_B_SUPPLY_INCIDENT" />);

    fireEvent.click(screen.getByRole("button", { name: /Load telemetry/ }));
    expect(await screen.findByTestId("incident-window")).not.toBeNull();
  });

  it("supports filtering by metric", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(<TelemetryPanel />);

    fireEvent.click(screen.getByRole("button", { name: /Load telemetry/ }));
    await screen.findByTestId("telemetry-chart");

    // default metric is pressure
    expect(screen.getByText("Pressure")).not.toBeNull();

    fireEvent.click(screen.getByRole("radio", { name: /Metric: Flow/ }));
    expect(screen.getByText("Flow")).not.toBeNull();
  });

  it("shows a non-incident run with no window overlay", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(normalTelemetry)),
    );
    render(<TelemetryPanel />);

    fireEvent.click(screen.getByRole("button", { name: /Load telemetry/ }));
    expect(await screen.findByTestId("telemetry-chart")).not.toBeNull();
    expect(screen.queryByTestId("incident-window")).toBeNull();
  });
});
