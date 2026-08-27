import { describe, expect, it } from "vitest";
import { buildZoneRows } from "./zones";
import { goldenResponse, normalResponse } from "../test/fixtures";
import type { AnalysisRunResponse } from "../types/analysis";

describe("buildZoneRows", () => {
  it("derives the affected zone severity from the response", () => {
    const rows = buildZoneRows(goldenResponse);
    expect(rows.map((row) => row.zoneId)).toEqual(["A", "B", "C", "D"]);

    const zoneB = rows.find((row) => row.zoneId === "B");
    expect(zoneB?.status).toBe("CRITICAL");
    expect(zoneB?.incident).not.toBeNull();

    const zoneA = rows.find((row) => row.zoneId === "A");
    expect(zoneA?.status).toBe("NORMAL");
    expect(zoneA?.incident).toBeNull();
  });

  it("marks every known zone NORMAL for a run with zero incidents", () => {
    const rows = buildZoneRows(normalResponse);
    expect(rows).toHaveLength(4);
    for (const row of rows) {
      expect(row.status).toBe("NORMAL");
      expect(row.incident).toBeNull();
    }
  });

  it("includes a zone that only appears in incidents", () => {
    const response: AnalysisRunResponse = {
      ...normalResponse,
      incidents: [
        {
          ...goldenResponse.incidents[0],
          incident: { ...goldenResponse.incidents[0].incident, zone_id: "X" },
        },
      ],
    };
    const rows = buildZoneRows(response);
    expect(rows.map((row) => row.zoneId)).toEqual(["A", "B", "C", "D", "X"]);
    expect(rows.find((row) => row.zoneId === "X")?.status).toBe("CRITICAL");
  });
});