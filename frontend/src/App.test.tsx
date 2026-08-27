import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { goldenResponse } from "./test/fixtures";

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body };
}

describe("App investigation flow", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("selects an incident and opens its investigation view", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/api/v1/analysis/run")) {
          return jsonResponse(goldenResponse);
        }
        if (url.endsWith("/health")) {
          return jsonResponse({ status: "ok" });
        }
        return jsonResponse({}, false, 404);
      }),
    );

    render(<App />);

    fireEvent.click(
      screen.getByRole("button", { name: /ZONE_B_SUPPLY_INCIDENT/ }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Simulate Water Incident/ }),
    );

    const investigate = await screen.findByRole("button", {
      name: /Open investigation/,
    });
    fireEvent.click(investigate);

    expect(
      await screen.findByRole("heading", { name: "Incident Investigation" }),
    ).not.toBeNull();
    expect(
      screen.getByText("ZONE B / WATER LOSS / CRITICAL"),
    ).not.toBeNull();
    expect(screen.getByText("91.52")).not.toBeNull();
    expect(
      screen.getByText("AI analysis unavailable — deterministic analysis remains available."),
    ).not.toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: /Back to Operations/ }),
    );
    expect(
      screen.getByRole("heading", { name: "Network Command View" }),
    ).not.toBeNull();
  });
});