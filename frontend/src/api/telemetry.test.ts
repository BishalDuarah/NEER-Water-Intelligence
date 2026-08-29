import { afterEach, describe, expect, it, vi } from "vitest";
import { TelemetryApiError, runTelemetry } from "./telemetry";
import { goldenTelemetry } from "../test/telemetryFixtures";

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

describe("runTelemetry", () => {
  it("POSTs the request as JSON to /api/v1/telemetry/run", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockFetchResponse(goldenTelemetry));
    vi.stubGlobal("fetch", fetchMock);

    await runTelemetry({ seed: 42, days: 1, scenario: "ZONE_B_SUPPLY_INCIDENT" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/telemetry/run");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      seed: 42,
      days: 1,
      scenario: "ZONE_B_SUPPLY_INCIDENT",
    });
  });

  it("omits reference_seed and a null scenario from the request body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockFetchResponse(goldenTelemetry));
    vi.stubGlobal("fetch", fetchMock);

    await runTelemetry({ seed: 42, days: 1 });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/telemetry/run");
    const body = JSON.parse(init.body);
    expect(body).toEqual({ seed: 42, days: 1 });
    expect("reference_seed" in body).toBe(false);
  });

  it("returns the parsed telemetry response on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockFetchResponse(normalTelemetrySlice())),
    );
    const result = await runTelemetry({ seed: 42, days: 1 });
    expect(result.run.seed).toBe(42);
    expect(result.zones).toHaveLength(4);
    expect(result.measurements.length).toBeGreaterThan(0);
    expect(result.scenarios).toEqual([]);
  });

  it("maps HTTP 422 to an invalid-request error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockFetchResponse({}, 422)));
    const promise = runTelemetry({ seed: 42, days: 1, scenario: "NOPE" });
    await expect(promise).rejects.toThrow(/rejected as invalid/);
    const error = (await promise.catch((e: unknown) => e)) as TelemetryApiError;
    expect(error).toBeInstanceOf(TelemetryApiError);
    expect(error.status).toBe(422);
  });

  it("maps HTTP 500 to a service-failure error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockFetchResponse({}, 500)));
    await expect(
      runTelemetry({ seed: 42, days: 1 }),
    ).rejects.toThrow(/service failed/);
  });

  it("maps a network failure to a reachability error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));
    await expect(
      runTelemetry({ seed: 42, days: 1 }),
    ).rejects.toThrow(/Could not reach the NEER backend/);
  });

  it("rejects a malformed response shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockFetchResponse({ not: "telemetry" })),
    );
    await expect(
      runTelemetry({ seed: 42, days: 1 }),
    ).rejects.toThrow(/unexpected response shape/);
  });
});

function normalTelemetrySlice() {
  return {
    run: {
      run_id: "telemetry-42-1-normal",
      seed: 42,
      days: 1,
      scenario: null,
      data_source: "deterministic-simulation" as const,
      window_hours: 24,
      zone_count: 4,
      measurement_count: 1,
      ran_at: "2026-08-28T01:36:00Z",
    },
    zones: [
      { zone_id: "A", name: "Zone A", district: "Central", area_sq_km: 18.5, estimated_population: 45000 },
      { zone_id: "B", name: "Zone B", district: "Riverside", area_sq_km: 12.0, estimated_population: 32000 },
      { zone_id: "C", name: "Zone C", district: "North Industrial", area_sq_km: 22.3, estimated_population: 18000 },
      { zone_id: "D", name: "Zone D", district: "East Suburbs", area_sq_km: 30.1, estimated_population: 52000 },
    ],
    measurements: [
      {
        timestamp: "2026-01-01T06:00:00Z",
        zone_id: "A",
        metric: "pressure",
        value: 4.295,
        unit: "bar",
      },
    ],
    scenarios: [],
  };
}
