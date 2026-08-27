import type { AnalysisIncidentOut } from "../types/analysis";
import { EmptyIncidentsPanel } from "./AnalysisStates";
import { IncidentRow } from "./IncidentRow";
import { ShieldCheckIcon } from "./icons";

interface IncidentQueueProps {
  incidents: AnalysisIncidentOut[];
  title?: string;
  subtitle?: string;
  onSelect?: (incidentId: string) => void;
}

export function IncidentQueue({
  incidents,
  title = "Active Incidents",
  subtitle = "Correlated, risk-ranked events awaiting response",
  onSelect,
}: IncidentQueueProps) {
  return (
    <section className="panel p-5" aria-label="Incident queue">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="label-mono">Response queue</p>
          <h2 className="mt-1 text-sm font-semibold">{title}</h2>
          <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
        </div>
        <ShieldCheckIcon className="size-4 text-primary" />
      </div>
      {incidents.length === 0 ? (
        <EmptyIncidentsPanel />
      ) : (
        <div className="mt-4 flex flex-col gap-3" data-testid="incident-queue">
          {incidents.map((item) => (
            <IncidentRow
              key={item.incident.incident_id}
              item={item}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </section>
  );
}