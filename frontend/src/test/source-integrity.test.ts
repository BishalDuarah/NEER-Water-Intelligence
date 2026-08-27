import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC_ROOT = join(__dirname, "..");

function isProductionSource(file: string): boolean {
  if (file.endsWith(".test.ts") || file.endsWith(".test.tsx")) return false;
  return file.endsWith(".ts") || file.endsWith(".tsx");
}

function collectFiles(directory: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(directory)) {
    if (entry === "test") continue;
    const full = join(directory, entry);
    if (statSync(full).isDirectory()) {
      files.push(...collectFiles(full));
    } else if (isProductionSource(full)) {
      files.push(full);
    }
  }
  return files;
}

describe("production source integrity", () => {
  it("contains no hardcoded golden incident values", () => {
    const forbidden = ["91.52", "0.9918", "0.985", "32000"];
    const offenders: string[] = [];
    for (const file of collectFiles(SRC_ROOT)) {
      const content = readFileSync(file, "utf8");
      for (const token of forbidden) {
        if (content.includes(token)) {
          offenders.push(`${file} contains "${token}"`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("contains no deterministic risk/severity-weight constants", () => {
    const forbidden = ["0.30", "0.20", "0.10", "0.40"];
    const offenders: string[] = [];
    for (const file of collectFiles(SRC_ROOT)) {
      const content = readFileSync(file, "utf8");
      for (const token of forbidden) {
        if (content.includes(token)) {
          offenders.push(`${file} contains "${token}"`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it("defines the demo scenario id in exactly one production file", () => {
    const scenarioToken = "ZONE_B_SUPPLY_INCIDENT";
    const matches = collectFiles(SRC_ROOT).filter((file) =>
      readFileSync(file, "utf8").includes(scenarioToken),
    );
    expect(matches).toEqual([join(SRC_ROOT, "types", "analysis.ts")]);
  });
});