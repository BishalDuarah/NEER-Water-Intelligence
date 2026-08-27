import { useState } from "react";
import { AppShell } from "./components/AppShell";
import type { AppTab } from "./components/AppShell";
import { BackendStatusPill } from "./components/BackendStatusPill";
import { useAnalysis } from "./hooks/useAnalysis";
import { ViewRouter } from "./views/ViewRouter";

export default function App() {
  const { state, run } = useAnalysis();
  const [tab, setTab] = useState<AppTab>("operations");

  return (
    <AppShell
      activeTab={tab}
      onNavigate={setTab}
      footer={<BackendStatusPill />}
    >
      <ViewRouter tab={tab} state={state} onRun={run} />
    </AppShell>
  );
}