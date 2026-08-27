import { describe, expect, it } from "vitest";
import {
  directionIndicator,
  formatConfidencePair,
  formatConfidencePercent,
  formatDateTime,
  formatDuration,
  formatIncidentType,
  formatPopulation,
  formatRisk,
  networkStatusFor,
  toneClasses,
  toneFor,
} from "./presentation";

describe("presentation helpers", () => {
  it("formats risk to two decimals", () => {
    expect(formatRisk(91.52)).toBe("91.52");
    expect(formatRisk(0.1)).toBe("0.10");
  });

  it("formats confidence as a percent with one decimal", () => {
    expect(formatConfidencePercent(0.9918)).toBe("99.2%");
    expect(formatConfidencePercent(0.5)).toBe("50.0%");
  });

  it("formats confidence as a precise decimal plus percent pair", () => {
    expect(formatConfidencePair(0.9918)).toBe("0.9918 / 99.18%");
    expect(formatConfidencePair(0.5)).toBe("0.5000 / 50.00%");
  });

  it("maps API signal directions to glyphs without changing the token", () => {
    expect(directionIndicator("above")).toBe("\u2191");
    expect(directionIndicator("below")).toBe("\u2193");
    expect(directionIndicator("neutral")).toBe("\u2192");
    expect(directionIndicator("unknown")).toBe("\u2014");
  });

  it("formats durations", () => {
    expect(formatDuration(0)).toBe("0m");
    expect(formatDuration(45)).toBe("45m");
    expect(formatDuration(345)).toBe("5h 45m");
    expect(formatDuration(120)).toBe("2h");
  });

  it("formats population with thousands separators", () => {
    expect(formatPopulation(32000)).toBe("32,000");
    expect(formatPopulation(null)).toBe("Unknown");
  });

  it("falls back to the raw timestamp when unparseable", () => {
    expect(formatDateTime("not-a-date")).toBe("not-a-date");
  });

  it("maps incident types to title case", () => {
    expect(formatIncidentType("WATER_LOSS")).toBe("Water Loss");
    expect(formatIncidentType("SUPPLY_DISRUPTION")).toBe("Supply Disruption");
  });

  it("maps statuses to semantic tones", () => {
    expect(toneFor("NORMAL")).toBe("ok");
    expect(toneFor("LOW")).toBe("ok");
    expect(toneFor("MEDIUM")).toBe("warn");
    expect(toneFor("HIGH")).toBe("danger");
    expect(toneFor("CRITICAL")).toBe("danger");
  });

  it("returns tailwind chip classes per tone", () => {
    expect(toneClasses("ok")).toContain("bg-ok/15");
    expect(toneClasses("warn")).toContain("border-warn/40");
    expect(toneClasses("danger")).toContain("bg-destructive/15");
  });

  it("derives the network status from incident severities", () => {
    expect(networkStatusFor([])).toBe("Stable");
    expect(networkStatusFor(["LOW"])).toBe("Watch");
    expect(networkStatusFor(["MEDIUM", "MEDIUM"])).toBe("Watch");
    expect(networkStatusFor(["HIGH"])).toBe("Alert");
    expect(networkStatusFor(["CRITICAL", "LOW"])).toBe("Alert");
  });
});