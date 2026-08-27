// @vitest-environment node
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { runAnalysis } from "../api/analysis";
import { OperationsView } from "../views/OperationsView";
import { IncidentInvestigationView } from "../views/IncidentInvestigationView";
import type { AnalysisState } from "../hooks/useAnalysis";

const live = process.env.NEER_LIVE_INTEGRATION === "1";

const run = describe.skipIf(!live);

run("live backend integration (requires NEER_LIVE_INTEGRATION=1)", () => {
  it("runs a real golden analysis and renders it in the dashboard", async () => {
    const result = await runAnalysis({
      seed: 42,
      days: 1,
      scenario: "ZONE_B_SUPPLY_INCIDENT",
      reference_seed: 99,
    });

    expect(result.summary.incidents).toBe(1);
    const item = result.incidents[0];
    expect(item.incident.zone_id).toBe("B");
    expect(item.incident.incident_type).toBe("WATER_LOSS");
    expect(item.incident.severity).toBe("CRITICAL");
    expect(item.incident.risk_score).toBeCloseTo(91.52, 1);
    expect(item.evidence.evidence_score).toBeCloseTo(0.985, 2);

    const state: AnalysisState = { status: "success", result };
    const html = renderToStaticMarkup(
      <OperationsView state={state} onRun={() => {}} />,
    );
    expect(html).toContain("Zone B");
    expect(html).toContain("Water Loss");
    expect(html).toContain("CRITICAL");
    expect(html).toContain("91.52");
    expect(html).toContain("Network Status: Alert");
    expect(html).toContain("AI analysis unavailable");
  }, 30000);

  it("renders the investigation view for a real golden incident", async () => {
    const result = await runAnalysis({
      seed: 42,
      days: 1,
      scenario: "ZONE_B_SUPPLY_INCIDENT",
      reference_seed: 99,
    });

    const incident = result.incidents[0];
    expect(incident).toBeDefined();
    expect(incident.incident.incident_id).toBe("INC-B-20260101T060000Z");
    expect(incident.incident.confidence).toBeCloseTo(0.9918, 3);
    expect(incident.evidence.temporal_coherence).toBeCloseTo(1.0, 2);
    expect(incident.evidence.spatial_coherence).toBeCloseTo(1.0, 2);
    expect(incident.evidence.signal_diversity).toBeCloseTo(1.0, 2);
    expect(incident.evidence.persistence_minutes).toBe(345);
    expect(incident.evidence.sensor_anomaly_count).toBe(89);
    expect(incident.evidence.citizen_report_count).toBe(12);

    const html = renderToStaticMarkup(
      <IncidentInvestigationView incident={incident} onBack={() => {}} />,
    );
    expect(html).toContain("ZONE B / WATER LOSS / CRITICAL");
    expect(html).toContain("91.52");
    expect(html).toContain("0.9918 / 99.18%");
    expect(html).toContain("32,000");
    expect(html).toContain("345 minutes");
    expect(html).toContain("No infrastructure action is executed by this interface.");
    expect(
      html.includes("AI analysis unavailable") ||
        html.includes("AI-assisted interpretation"),
    ).toBe(true);
  }, 30000);

  it("runs a normal analysis and renders zero incidents", async () => {
    const result = await runAnalysis({
      seed: 42,
      days: 1,
      scenario: null,
      reference_seed: 99,
    });

    expect(result.summary.incidents).toBe(0);
    expect(result.summary.zones).toBe(4);

    const state: AnalysisState = { status: "success", result };
    const html = renderToStaticMarkup(
      <OperationsView state={state} onRun={() => {}} />,
    );
    expect(html).toContain("Network Status: Stable");
    expect(html).toContain("No active incidents. Network signals nominal across all monitored zones.");
  }, 30000);
});