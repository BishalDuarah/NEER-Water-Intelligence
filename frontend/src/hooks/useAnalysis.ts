import { useCallback, useRef, useState } from "react";
import { AnalysisApiError, runAnalysis } from "../api/analysis";
import type { AnalysisRunRequest, AnalysisRunResponse } from "../types/analysis";

export type AnalysisState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: AnalysisRunResponse }
  | { status: "error"; message: string };

export interface UseAnalysisResult {
  state: AnalysisState;
  run: (request: AnalysisRunRequest) => Promise<void>;
}

export function useAnalysis(): UseAnalysisResult {
  const [state, setState] = useState<AnalysisState>({ status: "idle" });
  const runningRef = useRef(false);

  const run = useCallback(async (request: AnalysisRunRequest) => {
    if (runningRef.current) return;
    runningRef.current = true;
    setState({ status: "loading" });

    try {
      const result = await runAnalysis(request);
      setState({ status: "success", result });
    } catch (error) {
      setState({
        status: "error",
        message:
          error instanceof AnalysisApiError
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