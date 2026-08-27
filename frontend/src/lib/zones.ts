import type { AnalysisIncidentOut, AnalysisRunResponse } from "../types/analysis";
import type { ZoneStatus } from "./presentation";

export interface ZoneRow {
  zoneId: string;
  status: ZoneStatus;
  incident: AnalysisIncidentOut | null;
}

export const KNOWN_ZONES = ["A", "B", "C", "D"];

function zoneHasIncident(incidents: AnalysisIncidentOut[], zoneId: string) {
  return incidents.find((item) => item.incident.zone_id === zoneId) ?? null;
}

export function buildZoneRows(
  response: AnalysisRunResponse,
  knownZones: string[] = KNOWN_ZONES,
): ZoneRow[] {
  const zoneIds = new Set<string>([
    ...knownZones,
    ...response.incidents.map((item) => item.incident.zone_id),
  ]);

  return [...zoneIds]
    .sort()
    .map((zoneId) => {
      const incident = zoneHasIncident(response.incidents, zoneId);
      return {
        zoneId,
        status: incident ? incident.incident.severity : ("NORMAL" as const),
        incident,
      };
    });
}