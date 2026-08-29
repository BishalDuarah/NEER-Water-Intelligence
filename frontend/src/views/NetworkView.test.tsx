import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NetworkView } from "./NetworkView";
import { goldenTelemetry } from "../test/telemetryFixtures";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NetworkView", () => {
  it("auto-loads default telemetry and renders a chart per zone", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(<NetworkView />);

    expect(await screen.findByLabelText("Telemetry chart grid")).not.toBeNull();
    expect(screen.getAllByTestId("telemetry-chart")).toHaveLength(4);
    expect(screen.getByText("Zone A")).not.toBeNull();
    expect(screen.getByText("Zone B")).not.toBeNull();
  });

  it("exposes zone and metric filters that change the focused zone", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(<NetworkView />);

    await screen.findByLabelText("Telemetry chart grid");
    fireEvent.click(screen.getByRole("radio", { name: "Zone: Zone A" }));
    fireEvent.click(screen.getByRole("radio", { name: "Metric: Flow" }));
    expect(screen.getAllByTestId("telemetry-line").length).toBeGreaterThan(0);
  });

  it("shows the incident window note and overlay when a scenario runs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(<NetworkView />);

    await screen.findByLabelText("Telemetry chart grid");
    expect(screen.getByTestId("incident-window")).not.toBeNull();
  });

  it("supports running with the supply incident scenario", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(goldenTelemetry));
    vi.stubGlobal("fetch", fetchMock);
    render(<NetworkView />);

    await screen.findByLabelText("Telemetry chart grid");

    fireEvent.click(
      screen.getByRole("button", { name: "ZONE_B_SUPPLY_INCIDENT" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Run telemetry" }));

    const lastCall = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    expect(JSON.parse(lastCall[1].body)).toEqual({
      seed: 42,
      days: 1,
      scenario: "ZONE_B_SUPPLY_INCIDENT",
    });
  });

  it("renders an error state when the backend is unreachable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("failed")),
    );
    render(<NetworkView />);

    expect(await screen.findByText("Telemetry failed.")).not.toBeNull();
  });
});
