// @vitest-environment node
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { runAnalysis } from "../api/analysis";
import { OperationsView } from "../views/OperationsView";
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