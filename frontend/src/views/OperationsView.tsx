import { useRef } from "react";
import type { AnalysisRunRequest } from "../types/analysis";
import type { AnalysisState } from "../hooks/useAnalysis";
import { buildZoneRows } from "../lib/zones";
import { networkStatusFor } from "../lib/presentation";
import { NetworkStatusPill } from "../components/StatusPill";
import { SimulationEngine } from "../components/SimulationEngine";
import { StatPanel } from "../components/StatPanel";
import { ZoneHealthPanel } from "../components/ZoneHealthPanel";
import { TelemetryPanel } from "../components/TelemetryPanel";
import { IncidentQueue } from "../components/IncidentQueue";
import { CitizenReportsPanel } from "../components/CitizenReportsPanel";
import { IdlePanel, LoadingPanel, ErrorPanel } from "../components/AnalysisStates";

interface OperationsViewProps {
  state: AnalysisState;
  onRun: (request: AnalysisRunRequest) => void;
}

export function OperationsView({ state, onRun }: OperationsViewProps) {
  const lastRequestRef = useRef<AnalysisRunRequest | null>(null);

  const handleRun = (request: AnalysisRunRequest) => {
    lastRequestRef.current = request;
    onRun(request);
  };

  const handleRetry = () => {
    if (lastRequestRef.current) onRun(lastRequestRef.current);
  };

  const severityList =
    state.status === "success"
      ? (state.result.incidents.map(
          (item) => item.incident.severity,
        ) as ("LOW" | "MEDIUM" | "HIGH" | "CRITICAL")[])
      : [];

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label-mono">Operations dashboard</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            Network Command View
          </h1>
        </div>
        {state.status === "success" ? (
          <NetworkStatusPill status={networkStatusFor(severityList)} />
        ) : (
          <span className="chip border-border/50 text-muted-foreground">
            Awaiting analysis
          </span>
        )}
      </header>

      <SimulationEngine loading={state.status === "loading"} onRun={handleRun} />

      {state.status === "idle" && <IdlePanel />}
      {state.status === "loading" && <LoadingPanel />}
      {state.status === "error" && (
        <div>
          <p className="label-mono">Latest attempt</p>
          <ErrorPanel message={state.message} onRetry={handleRetry} />
        </div>
      )}

      {state.status === "success" && (
        <>
          <section
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5"
            aria-label="Network summary"
          >
            <StatPanel
              label="Overall Network Status"
              value={networkStatusFor(severityList)}
              note="Derived from correlated incident severity"
              tone={
                networkStatusFor(severityList) === "Stable"
                  ? "ok"
                  : networkStatusFor(severityList) === "Watch"
                    ? "warn"
                    : "danger"
              }
            />
            <StatPanel
              label="Zones Monitored"
              value={String(buildZoneRows(state.result).length)}
              note="DMAs covered by the analysis window"
            />
            <StatPanel
              label="Active Incidents"
              value={String(state.result.incidents.length)}
              note="Correlated events awaiting response"
            />
            <StatPanel
              label="Critical Incidents"
              value={String(
                state.result.incidents.filter(
                  (item) => item.incident.severity === "CRITICAL",
                ).length,
              )}
              note="Highest-risk correlated events"
            />
            <StatPanel
              label="Anomalies Detected"
              value={String(
                state.result.incidents.reduce(
                  (sum, item) => sum + item.evidence.sensor_anomaly_count,
                  0,
                ),
              )}
              note="Flags included in incident evidence"
            />
          </section>

          <section
            className="grid gap-4 lg:grid-cols-3"
            aria-label="Zone monitoring"
          >
            <div className="lg:col-span-2">
              <TelemetryPanel />
            </div>
            <ZoneHealthPanel zones={buildZoneRows(state.result)} />
          </section>

          <section
            className="grid gap-4 lg:grid-cols-3"
            aria-label="Incident management"
          >
            <div className="lg:col-span-2">
              <IncidentQueue incidents={state.result.incidents} />
            </div>
            <CitizenReportsPanel incidents={state.result.incidents} />
          </section>
        </>
      )}
    </div>
  );
}