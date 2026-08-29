import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useTelemetry } from "./useTelemetry";
import { goldenTelemetry } from "../test/telemetryFixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useTelemetry", () => {
  it("starts idle", () => {
    const { result } = renderHook(() => useTelemetry());
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("moves to loading, then success with the returned response", async () => {
    let resolveFetch: (value: unknown) => void = () => {};
    const fetchMock = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useTelemetry());

    let runPromise: Promise<void>;
    act(() => {
      runPromise = result.current.run({ seed: 42, days: 1, scenario: null });
    });

    expect(result.current.state).toEqual({ status: "loading" });

    await act(async () => {
      resolveFetch({ ok: true, status: 200, json: async () => goldenTelemetry });
      await runPromise;
    });

    expect(result.current.state.status).toBe("success");
    if (result.current.state.status === "success") {
      expect(result.current.state.result.run.seed).toBe(42);
      expect(result.current.state.result.measurements.length).toBeGreaterThan(0);
    }
  });

  it("stores a friendly error message on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("boom")));
    const { result } = renderHook(() => useTelemetry());

    await act(async () => {
      await result.current.run({ seed: 42, days: 1 });
    });

    expect(result.current.state).toEqual({
      status: "error",
      message: "Could not reach the NEER backend. Start it and try again.",
    });
  });

  it("ignores a duplicate run while loading", async () => {
    const fetchMock = vi.fn(() => new Promise<unknown>(() => {}));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useTelemetry());

    act(() => {
      result.current.run({ seed: 42, days: 1 });
      result.current.run({ seed: 7, days: 1 });
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
