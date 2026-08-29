import { useCallback, useRef, useState } from "react";
import { TelemetryApiError, runTelemetry } from "../api/telemetry";
import type {
  TelemetryRunRequest,
  TelemetryRunResponse,
} from "../types/telemetry";

export type TelemetryState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: TelemetryRunResponse }
  | { status: "error"; message: string };

export interface UseTelemetryResult {
  state: TelemetryState;
  run: (request: TelemetryRunRequest) => Promise<void>;
}

export function useTelemetry(): UseTelemetryResult {
  const [state, setState] = useState<TelemetryState>({ status: "idle" });
  const runningRef = useRef(false);

  const run = useCallback(async (request: TelemetryRunRequest) => {
    if (runningRef.current) return;
    runningRef.current = true;
    setState({ status: "loading" });

    try {
      const result = await runTelemetry(request);
      setState({ status: "success", result });
    } catch (error) {
      setState({
        status: "error",
        message:
          error instanceof TelemetryApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : String(error),
      });
    } finally {
      runningRef.current = false;
    }
  }, []);

  return { state, run };
}
