import { useRef } from "react";
import type { AnalysisRunRequest } from "../types/analysis";
import type { AnalysisState } from "../hooks/useAnalysis";
import { SimulationEngine } from "../components/SimulationEngine";
import { IncidentQueue } from "../components/IncidentQueue";
import { IdlePanel, LoadingPanel, ErrorPanel } from "../components/AnalysisStates";

interface IncidentsViewProps {
  state: AnalysisState;
  onRun: (request: AnalysisRunRequest) => void;
}

export function IncidentsView({ state, onRun }: IncidentsViewProps) {
  const lastRequestRef = useRef<AnalysisRunRequest | null>(null);

  const handleRun = (request: AnalysisRunRequest) => {
    lastRequestRef.current = request;
    onRun(request);
  };

  const handleRetry = () => {
    if (lastRequestRef.current) onRun(lastRequestRef.current);
  };

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <header>
        <p className="label-mono">Incidents</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">
          NEER Response Queue
        </h1>
      </header>

      <SimulationEngine loading={state.status === "loading"} onRun={handleRun} />

      {state.status === "idle" && <IdlePanel />}
      {state.status === "loading" && <LoadingPanel />}
      {state.status === "error" && (
        <ErrorPanel message={state.message} onRetry={handleRetry} />
      )}
      {state.status === "success" && (
        <IncidentQueue
          incidents={state.result.incidents}
          title="All Incidents"
          subtitle="Every correlated event in the latest analysis run"
        />
      )}
    </div>
  );
}