import type { ZoneRow } from "../lib/zones";
import { SeverityChip } from "./SeverityChip";
import { ActivityIcon } from "./icons";

interface ZoneHealthPanelProps {
  zones: ZoneRow[];
}

export function ZoneHealthPanel({ zones }: ZoneHealthPanelProps) {
  return (
    <section className="panel p-5" aria-label="Zone health overview">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="label-mono">Network monitor</p>
          <h2 className="mt-1 text-sm font-semibold">Zone Health Overview</h2>
        </div>
        <ActivityIcon className="size-4 text-primary" />
      </div>
      <ul className="mt-3 divide-y divide-border/70">
        {zones.map((zone) => (
          <li
            key={zone.zoneId}
            data-testid={`zone-${zone.zoneId}`}
            className="flex items-center justify-between gap-3 py-2.5"
          >
            <div className="min-w-0">
              <p className="font-mono text-sm font-medium">Zone {zone.zoneId}</p>
              <p className="text-xs text-muted-foreground">
                {zone.incident
                  ? "Incident active on this DMA"
                  : "No signals detected"}
              </p>
            </div>
            {zone.incident && (
              <p className="hidden max-w-[45%] truncate text-xs text-muted-foreground sm:block">
                {zone.incident.incident.incident_type.replace(/_/g, " ")}
              </p>
            )}
            <SeverityChip
              status={zone.status}
              label={zone.status === "NORMAL" ? "Normal" : zone.status}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}