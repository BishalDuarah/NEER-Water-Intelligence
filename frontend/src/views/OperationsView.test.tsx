import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OperationsView } from "./OperationsView";
import {
  aiResponse,
  goldenResponse,
  normalResponse,
} from "../test/fixtures";
import type { AnalysisRunRequest } from "../types/analysis";

const defaultRequest: AnalysisRunRequest = {
  seed: 42,
  days: 1,
  scenario: null,
  reference_seed: 99,
};

describe("OperationsView", () => {
  it("shows an idle prompt before any analysis", () => {
    render(<OperationsView state={{ status: "idle" }} onRun={() => {}} />);
    expect(
      screen.getByText(/No analysis has been run yet/),
    ).not.toBeNull();
    expect(
      screen.getByRole("button", { name: /Simulate Water Incident/ }),
    ).not.toBeNull();
  });

  it("shows a loading state while analyzing", () => {
    render(<OperationsView state={{ status: "loading" }} onRun={() => {}} />);
    expect(
      screen.getByText("Running deterministic analysis pipeline…"),
    ).not.toBeNull();
    expect(
      (screen.getByRole("button", { name: /Analyzing/ }) as HTMLButtonElement)
        .disabled,
    ).toBe(true);
  });

  it("shows the error message and retries the last request", () => {
    const onRun = vi.fn();
    const { rerender } = render(
      <OperationsView
        state={{ status: "success", result: goldenResponse }}
        onRun={onRun}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate Water Incident/ }),
    );
    rerender(
      <OperationsView
        state={{ status: "error", message: "Backend is down." }}
        onRun={onRun}
      />,
    );

    expect(screen.getByText("Backend is down.")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Try again/ }));
    expect(onRun).toHaveBeenCalledTimes(2);
    expect(onRun).toHaveBeenLastCalledWith(defaultRequest);
  });

  it("renders the golden Zone B incident values from the response", () => {
    render(
      <OperationsView
        state={{ status: "success", result: goldenResponse }}
        onRun={() => {}}
      />,
    );

    expect(screen.getByRole("heading", { name: "Network Command View" })).not.toBeNull();
    expect(screen.getByText(/Network Status: Alert/)).not.toBeNull();

    const stats = within(screen.getByLabelText("Network summary"));
    expect(stats.getByText("Alert")).not.toBeNull();
    expect(stats.getAllByText("1")).toHaveLength(2);
    expect(stats.getByText("89")).not.toBeNull();

    const zoneB = within(screen.getByTestId("zone-B"));
    expect(zoneB.getByText(/Zone B/)).not.toBeNull();
    expect(zoneB.getByText("WATER LOSS")).not.toBeNull();
    expect(zoneB.getByText("CRITICAL")).not.toBeNull();

    for (const zoneId of ["A", "C", "D"]) {
      const zone = within(screen.getByTestId(`zone-${zoneId}`));
      expect(zone.getByText("Normal")).not.toBeNull();
      expect(zone.getByText("No signals detected")).not.toBeNull();
    }

    const queue = within(screen.getByTestId("incident-queue"));
    expect(queue.getByText("91.52")).not.toBeNull();
    expect(queue.getByText("99.2%")).not.toBeNull();
    expect(queue.getByText("0.985")).not.toBeNull();
    expect(queue.getByText("5h 45m")).not.toBeNull();
    expect(queue.getByText("32,000")).not.toBeNull();
    expect(queue.getByText("DETECTED")).not.toBeNull();
    expect(queue.getAllByText(/below_baseline/).length).toBeGreaterThan(0);

    const reports = within(screen.getByLabelText("Citizen reports"));
    expect(reports.getByText(/· 12 reports/)).not.toBeNull();
  });

  it("surfaces the fallback messaging when AI is unavailable", () => {
    render(
      <OperationsView
        state={{ status: "success", result: goldenResponse }}
        onRun={() => {}}
      />,
    );
    expect(
      screen.getByText(
        "AI analysis unavailable — deterministic analysis remains available.",
      ),
    ).not.toBeNull();
    expect(
      screen.getByText("Fallback reason: PROVIDER_UNAVAILABLE"),
    ).not.toBeNull();
  });

  it("distinguishes a real AI source with its summary", () => {
    render(
      <OperationsView
        state={{ status: "success", result: aiResponse }}
        onRun={() => {}}
      />,
    );
    expect(screen.getByText(/AI analysis available/)).not.toBeNull();
    expect(
      screen.getByText(
        "Cross-zone evidence supports a water loss; recommend operator inspection of the Zone B distribution inlet.",
      ),
    ).not.toBeNull();
    expect(
      screen.queryByText(
        "AI analysis unavailable — deterministic analysis remains available.",
      ),
    ).toBeNull();
  });

  it("renders four NORMAL zones and an empty queue for a normal run", () => {
    render(
      <OperationsView
        state={{ status: "success", result: normalResponse }}
        onRun={() => {}}
      />,
    );

    expect(screen.getByText(/Network Status: Stable/)).not.toBeNull();
    expect(screen.getAllByText("Normal")).toHaveLength(4);
    expect(
      screen.getByText("No active incidents. Network signals nominal across all monitored zones."),
    ).not.toBeNull();
    expect(
      screen.getByText("No citizen reports associated with active incidents."),
    ).not.toBeNull();
    for (const zoneId of ["A", "B", "C", "D"]) {
      expect(screen.getByTestId(`zone-${zoneId}`)).not.toBeNull();
    }
  });

  it("submits the selected scenario in the run request", () => {
    const onRun = vi.fn();
    render(<OperationsView state={{ status: "idle" }} onRun={onRun} />);

    fireEvent.click(
      screen.getByRole("button", { name: /Simulate Water Incident/ }),
    );
    expect(onRun).toHaveBeenLastCalledWith(defaultRequest);

    const scenarioButton = screen.getByRole("button", {
      name: /ZONE_B_SUPPLY_INCIDENT/,
    });
    expect(scenarioButton.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(scenarioButton);
    expect(scenarioButton.getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(
      screen.getByRole("button", { name: /Simulate Water Incident/ }),
    );
    expect(onRun).toHaveBeenLastCalledWith({
      ...defaultRequest,
      scenario: "ZONE_B_SUPPLY_INCIDENT",
    });
  });
});