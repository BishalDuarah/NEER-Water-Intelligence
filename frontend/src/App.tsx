import { useState } from "react";
import { AppShell } from "./components/AppShell";
import type { AppTab } from "./components/AppShell";
import { BackendStatusPill } from "./components/BackendStatusPill";
import { useAnalysis } from "./hooks/useAnalysis";
import { IncidentInvestigationView } from "./views/IncidentInvestigationView";
import { ViewRouter } from "./views/ViewRouter";

export default function App() {
  const { state, run } = useAnalysis();
  const [tab, setTab] = useState<AppTab>("operations");
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    null,
  );

  const handleNavigate = (next: AppTab) => {
    setTab(next);
    setSelectedIncidentId(null);
  };

  const investigating = selectedIncidentId !== null;
  const selectedIncident =
    state.status === "success"
      ? (state.result.incidents.find(
          (item) => item.incident.incident_id === selectedIncidentId,
        ) ?? null)
      : null;

  return (
    <AppShell
      activeTab={tab}
      onNavigate={handleNavigate}
      footer={<BackendStatusPill />}
    >
      {investigating ? (
        <IncidentInvestigationView
          incident={selectedIncident}
          onBack={() => setSelectedIncidentId(null)}
          run={state.status === "success" ? state.result.run : null}
        />
      ) : (
        <ViewRouter
          tab={tab}
          state={state}
          onRun={run}
          onSelectIncident={setSelectedIncidentId}
        />
      )}
    </AppShell>
  );
}