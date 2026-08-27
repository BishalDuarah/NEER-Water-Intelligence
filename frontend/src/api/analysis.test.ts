import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalysisApiError, runAnalysis } from "./analysis";
import { normalResponse } from "../test/fixtures";

function mockFetchResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("runAnalysis", () => {
  it("POSTs the request as JSON to /api/v1/analysis/run", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockFetchResponse(normalResponse));
    vi.stubGlobal("fetch", fetchMock);

    await runAnalysis({
      seed: 42,
      days: 1,
      scenario: "ZONE_B_SUPPLY_INCIDENT",
      reference_seed: 99,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/analysis/run");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      seed: 42,
      days: 1,
      scenario: "ZONE_B_SUPPLY_INCIDENT",
      reference_seed: 99,
    });
  });

  it("returns the parsed response on success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockFetchResponse(normalResponse)));
    const result = await runAnalysis({
      seed: 42,
      days: 1,
      scenario: null,
      reference_seed: 99,
    });
    expect(result.run.seed).toBe(42);
    expect(result.incidents).toHaveLength(0);
    expect(result.summary.zones).toBe(4);
  });

  it("maps HTTP 422 to an invalid-request error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockFetchResponse({}, 422)));
    const promise = runAnalysis({
      seed: 42,
      days: 1,
      scenario: "NOPE",
      reference_seed: 99,
    });
    await expect(promise).rejects.toThrow(/rejected as invalid/);
    const error = (await promise.catch((e: unknown) => e)) as AnalysisApiError;
    expect(error).toBeInstanceOf(AnalysisApiError);
    expect(error.status).toBe(422);
  });

  it("maps HTTP 500 to a service-failure error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockFetchResponse({}, 500)));
    await expect(
      runAnalysis({ seed: 42, days: 1, scenario: null, reference_seed: 99 }),
    ).rejects.toThrow(/service failed/);
  });

  it("maps a network failure to a reachability error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));
    await expect(
      runAnalysis({ seed: 42, days: 1, scenario: null, reference_seed: 99 }),
    ).rejects.toThrow(/Could not reach the NEER backend/);
  });

  it("rejects a malformed response shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockFetchResponse({ not: "an analysis" })),
    );
    await expect(
      runAnalysis({ seed: 42, days: 1, scenario: null, reference_seed: 99 }),
    ).rejects.toThrow(/unexpected response shape/);
  });
});