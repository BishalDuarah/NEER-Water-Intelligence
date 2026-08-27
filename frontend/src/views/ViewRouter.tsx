import { NetworkView } from "./NetworkView";
import { OperationsView } from "./OperationsView";
import { IncidentsView } from "./IncidentsView";
import type { AppTab } from "../components/AppShell";
import type { AnalysisRunRequest } from "../types/analysis";
import type { AnalysisState } from "../hooks/useAnalysis";

interface ViewRouterProps {
  tab: AppTab;
  state: AnalysisState;
  onRun: (request: AnalysisRunRequest) => void;
  onSelectIncident?: (incidentId: string) => void;
}

export function ViewRouter({ tab, state, onRun, onSelectIncident }: ViewRouterProps) {
  switch (tab) {
    case "operations":
      return (
        <OperationsView
          state={state}
          onRun={onRun}
          onSelectIncident={onSelectIncident}
        />
      );
    case "incidents":
      return (
        <IncidentsView
          state={state}
          onRun={onRun}
          onSelectIncident={onSelectIncident}
        />
      );
    case "network":
      return <NetworkView />;
  }
}