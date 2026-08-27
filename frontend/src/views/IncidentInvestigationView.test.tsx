import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  aiResponse,
  goldenResponse,
} from "../test/fixtures";
import { IncidentInvestigationView } from "./IncidentInvestigationView";

const goldenIncident = goldenResponse.incidents[0];
const aiIncident = aiResponse.incidents[0];

describe("IncidentInvestigationView", () => {
  it("renders the golden Zone B incident values from the response", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Incident Investigation" }),
    ).not.toBeNull();
    expect(
      screen.getByText("ZONE B / WATER LOSS / CRITICAL"),
    ).not.toBeNull();
    expect(screen.getByText("INC-B-20260101T060000Z")).not.toBeNull();
    expect(screen.getByText("DETECTED")).not.toBeNull();

    const risk = within(screen.getByTestId("investigation-risk"));
    expect(risk.getByText("91.52")).not.toBeNull();
    expect(risk.getByText("0.9918 / 99.18%")).not.toBeNull();
    expect(risk.getByText("0.985")).not.toBeNull();
    expect(risk.getByText("5h 45m")).not.toBeNull();
    expect(risk.getByText("345 minutes")).not.toBeNull();
    expect(risk.getByText("32,000")).not.toBeNull();
    expect(risk.getByText("89")).not.toBeNull();
    expect(risk.getByText("12")).not.toBeNull();

    const correlation = within(screen.getByTestId("investigation-correlation"));
    expect(correlation.getByText("0.985")).not.toBeNull();
    expect(correlation.getByText("5h 45m")).not.toBeNull();
    expect(correlation.getByText("345 minutes")).not.toBeNull();
    expect(correlation.getAllByText("1.00")).toHaveLength(3);

    expect(
      screen.getByText("Multiple independent signals were observed together over time."),
    ).not.toBeNull();
    expect(
      screen.getByText(
        "Combined pressure, flow, consumption and quality anomalies with rising citizen reports exceed the correlation trigger for a supply interruption.",
      ),
    ).not.toBeNull();
  });

  it("renders the four contributing signals with directions from the API", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    const signals = within(screen.getByTestId("investigation-signals"));
    const flow = signals.getByRole("row", { name: /flow/ });
    expect(flow.textContent).toContain("above");
    expect(flow.textContent).toContain("22");
    expect(flow.textContent).toContain("8.16");

    const pressure = signals.getByRole("row", { name: /pressure/ });
    expect(pressure.textContent).toContain("below");
    expect(pressure.textContent).toContain("24");
    expect(pressure.textContent).toContain("-32.01");

    const quality = signals.getByRole("row", { name: /quality/ });
    expect(quality.textContent).toContain("below");
    expect(quality.textContent).toContain("20");

    const consumption = signals.getByRole("row", { name: /consumption/ });
    expect(consumption.textContent).toContain("below");
    expect(consumption.textContent).toContain("23");
  });

  it("labels a real AI source as AI-assisted interpretation", () => {
    render(
      <IncidentInvestigationView incident={aiIncident} onBack={() => {}} />,
    );

    expect(
      screen.getByRole("heading", { name: "AI Incident Analysis" }),
    ).not.toBeNull();
    expect(
      screen.getByText("AI-assisted interpretation"),
    ).not.toBeNull();
    expect(
      screen.queryByText("AI analysis unavailable — deterministic analysis remains available."),
    ).toBeNull();
    expect(
      screen.queryByText("Deterministic fallback analysis"),
    ).toBeNull();
  });

  it("distinguishes a deterministic fallback from an AI analysis", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Incident Analysis (Deterministic Fallback)",
      }),
    ).not.toBeNull();
    expect(
      screen.getByText("Deterministic fallback analysis"),
    ).not.toBeNull();
    expect(
      screen.getByText(
        "AI analysis unavailable — deterministic analysis remains available.",
      ),
    ).not.toBeNull();
    expect(screen.getByText("Fallback reason: PROVIDER_UNAVAILABLE")).not.toBeNull();
  });

  it("renders the AI summary and evidence interpretation", () => {
    render(
      <IncidentInvestigationView incident={aiIncident} onBack={() => {}} />,
    );

    expect(
      screen.getByText(
        "Cross-zone evidence supports a water loss; recommend operator inspection of the Zone B distribution inlet.",
      ),
    ).not.toBeNull();
    expect(
      screen.getByText(
        "Flow, pressure, quality and consumption signals deviate together within a short window, and citizen reports rise in the same period — characteristic of a supply-side disturbance in one zone.",
      ),
    ).not.toBeNull();
  });

  it("renders possible causes with their framing preserved", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    expect(
      screen.getByText("Burst or significant leak on a transmission line feeding Zone B"),
    ).not.toBeNull();
    expect(screen.getByText("plausible")).not.toBeNull();
    expect(screen.getByText("Sustained pressure drop")).not.toBeNull();
    expect(screen.getByText("Above-baseline flow")).not.toBeNull();
  });

  it("renders suggested investigation actions without executing them", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    expect(screen.getByText("Suggested investigation")).not.toBeNull();
    expect(
      screen.getByText(
        "Suggested steps for an operator to verify — nothing is executed by this platform.",
      ),
    ).not.toBeNull();
    expect(
      screen.getByText("Confirm isolation valve positions at the Zone B district meter"),
    ).not.toBeNull();
    expect(screen.getByText("Priority 80")).not.toBeNull();
  });

  it("renders response options strictly as advisory", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    expect(screen.getByText("Advisory response options")).not.toBeNull();
    expect(
      screen.getByText(
        "Operator decision required. These are suggestions, not commands.",
      ),
    ).not.toBeNull();
    expect(screen.getByText("Advisory")).not.toBeNull();
    expect(
      screen.getByText("Prepare for planned supply isolation under operator command"),
    ).not.toBeNull();
    expect(
      screen.getByText("Only an operator may act; the platform never controls valves."),
    ).not.toBeNull();
  });

  it("renders uncertainty and separates confidence from cause certainty", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    expect(
      screen.getByText(
        "Assessment confidence: 99.18% — confidence describes how strongly the deterministic evidence fits the classification, not the probability of a specific physical cause.",
      ),
    ).not.toBeNull();
    expect(screen.getByText("Pressure drop")).not.toBeNull();
    expect(screen.getByText("Exact leak location")).not.toBeNull();
    expect(screen.getByText("SCADA alarm logs for the district meter")).not.toBeNull();
  });

  it("renders the safety notice and safety notes", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    expect(screen.getByText(/Decision support only\./)).not.toBeNull();
    expect(
      screen.getByText(
        /NEER provides evidence-based analysis and advisory recommendations\. No infrastructure action is executed by this interface\./,
      ),
    ).not.toBeNull();
    expect(
      screen.getByText(
        "No autonomous action. All recommendations require human operator approval.",
      ),
    ).not.toBeNull();
  });

  it("never lets AI fields overwrite deterministic values", () => {
    render(
      <IncidentInvestigationView incident={aiIncident} onBack={() => {}} />,
    );

    expect(screen.getByText("91.52")).not.toBeNull();
    expect(screen.getByText("ZONE B / WATER LOSS / CRITICAL")).not.toBeNull();
    expect(screen.getByText("CRITICAL")).not.toBeNull();
    expect(screen.getByText("0.9918 / 99.18%")).not.toBeNull();
  });

  it("exposes no infrastructure-control buttons", () => {
    render(
      <IncidentInvestigationView
        incident={goldenIncident}
        onBack={() => {}}
      />,
    );

    for (const name of [/Shut/i, /Stop pump/i, /Dispatch/i, /Isolate/i]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    expect(
      screen.queryByRole("button", { name: /Simulate Water Incident/ }),
    ).toBeNull();
  });

  it("returns to the operations dashboard via the back button", () => {
    const onBack = vi.fn();
    render(
      <IncidentInvestigationView incident={goldenIncident} onBack={onBack} />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /Back to Operations/ }),
    );
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("shows a safe empty state when no incident is available", () => {
    render(<IncidentInvestigationView incident={null} onBack={() => {}} />);

    expect(
      screen.getByText("No incidents available for investigation."),
    ).not.toBeNull();
    expect(
      screen.getByText("Run an analysis with a detected incident to inspect evidence."),
    ).not.toBeNull();
    expect(
      screen.getByRole("button", { name: /Back to Operations/ }),
    ).not.toBeNull();
  });
});