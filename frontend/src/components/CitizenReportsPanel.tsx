import { formatDateTime } from "../lib/presentation";
import type { AnalysisIncidentOut } from "../types/analysis";
import { MessagesSquareIcon } from "./icons";

interface CitizenReportsPanelProps {
  incidents: AnalysisIncidentOut[];
}

interface ReportRow {
  zoneId: string;
  count: number;
  startTime: string;
  incidentType: string;
}

export function CitizenReportsPanel({ incidents }: CitizenReportsPanelProps) {
  const rows: ReportRow[] = incidents.flatMap((item) =>
    item.evidence.citizen_report_count > 0
      ? [
          {
            zoneId: item.incident.zone_id,
            count: item.evidence.citizen_report_count,
            startTime: item.incident.start_time,
            incidentType: item.incident.incident_type,
          },
        ]
      : [],
  );

  return (
    <section className="panel p-5" aria-label="Citizen reports">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="label-mono">Crowd-sourced signal</p>
          <h2 className="mt-1 text-sm font-semibold">Citizen Reports</h2>
        </div>
        <MessagesSquareIcon className="size-4 text-primary" />
      </div>
      {rows.length === 0 ? (
        <div className="mt-4 flex items-center gap-3 rounded-md border border-border/70 bg-secondary/30 px-4 py-8 text-sm text-muted-foreground">
          <span aria-hidden="true" className="size-2 rounded-full bg-ok" />
          No citizen reports associated with active incidents.
        </div>
      ) : (
        <ul className="mt-3 divide-y divide-border/70">
          {rows.map((row) => (
            <li key={row.zoneId} className="py-3">
              <div className="flex items-baseline justify-between gap-2">
                <p className="font-mono text-sm">
                  <span className="text-primary">Zone {row.zoneId}</span>
                  <span className="text-muted-foreground"> · {row.count} reports</span>
                </p>
                <span className="font-mono text-xs text-muted-foreground">
                  {formatDateTime(row.startTime)}
                </span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Counted in the evidence for the{" "}
                {row.incidentType.replace(/_/g, " ").toLowerCase()} signal.
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}