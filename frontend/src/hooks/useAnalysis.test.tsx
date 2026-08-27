import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAnalysis } from "./useAnalysis";
import { normalResponse } from "../test/fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useAnalysis", () => {
  it("starts idle", () => {
    const { result } = renderHook(() => useAnalysis());
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

    const { result } = renderHook(() => useAnalysis());

    let runPromise: Promise<void>;
    act(() => {
      runPromise = result.current.run({
        seed: 42,
        days: 1,
        scenario: null,
        reference_seed: 99,
      });
    });

    expect(result.current.state).toEqual({ status: "loading" });

    await act(async () => {
      resolveFetch({ ok: true, status: 200, json: async () => normalResponse });
      await runPromise;
    });

    expect(result.current.state.status).toBe("success");
    if (result.current.state.status === "success") {
      expect(result.current.state.result.run.seed).toBe(42);
    }
  });

  it("stores a friendly error message on failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("boom")));
    const { result } = renderHook(() => useAnalysis());

    await act(async () => {
      await result.current.run({
        seed: 42,
        days: 1,
        scenario: null,
        reference_seed: 99,
      });
    });

    expect(result.current.state).toEqual({
      status: "error",
      message: "Could not reach the NEER backend. Start it and try again.",
    });
  });

  it("ignores a duplicate run while loading", async () => {
    const fetchMock = vi.fn(
      () => new Promise<unknown>(() => {}),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useAnalysis());

    act(() => {
      result.current.run({ seed: 42, days: 1, scenario: null, reference_seed: 99 });
      result.current.run({ seed: 7, days: 1, scenario: null, reference_seed: 99 });
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});