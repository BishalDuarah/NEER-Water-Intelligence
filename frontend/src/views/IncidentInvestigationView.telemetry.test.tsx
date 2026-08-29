import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IncidentInvestigationView } from "./IncidentInvestigationView";
import { goldenResponse } from "../test/fixtures";
import { goldenTelemetry } from "../test/telemetryFixtures";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body };
}

const incident = goldenResponse.incidents[0];
const run = goldenResponse.run;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("IncidentInvestigationView telemetry integration", () => {
  it("renders no telemetry section when no run metadata is provided", () => {
    render(<IncidentInvestigationView incident={incident} onBack={() => {}} />);
    expect(
      screen.queryByLabelText("Incident zone telemetry"),
    ).toBeNull();
  });

  it("loads the incident zone telemetry on demand from the analysis run", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(
      <IncidentInvestigationView
        incident={incident}
        onBack={() => {}}
        run={run}
      />,
    );

    expect(
      screen.getByLabelText("Incident zone telemetry"),
    ).not.toBeNull();
    expect(screen.queryByTestId("telemetry-chart")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Load telemetry/ }));

    expect(await screen.findByTestId("telemetry-chart")).not.toBeNull();
    expect(screen.getByTestId("incident-window")).not.toBeNull();
    expect(
      screen.getByText(/Incident window from scenario: 2026-01-01T06:00:00Z/),
    ).not.toBeNull();
  });

  it("keeps the deterministic incident values intact alongside telemetry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(goldenTelemetry)),
    );
    render(
      <IncidentInvestigationView
        incident={incident}
        onBack={() => {}}
        run={run}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Load telemetry/ }));
    await screen.findByTestId("telemetry-chart");
    expect(screen.getByText("91.52")).not.toBeNull();
    expect(screen.getByText("ZONE B / WATER LOSS / CRITICAL")).not.toBeNull();
  });
});
