import type { SeverityLabel } from "../types/analysis";

export type ZoneStatus = SeverityLabel | "NORMAL";

export type StatusTone = "ok" | "warn" | "danger";

const TONE_CLASSES: Record<StatusTone, string> = {
  ok: "bg-ok/15 text-ok border-ok/40",
  warn: "bg-warn/15 text-warn border-warn/40",
  danger: "bg-destructive/15 text-destructive border-destructive/40",
};

export function toneFor(status: ZoneStatus | SeverityLabel): StatusTone {
  switch (status) {
    case "NORMAL":
    case "LOW":
      return "ok";
    case "MEDIUM":
      return "warn";
    case "HIGH":
    case "CRITICAL":
      return "danger";
  }
}

export function toneClasses(tone: StatusTone): string {
  return TONE_CLASSES[tone];
}

export function formatRisk(riskScore: number): string {
  return riskScore.toFixed(2);
}

export function formatConfidencePercent(confidence: number): string {
  return `${(confidence * 100).toFixed(1)}%`;
}

export function formatDuration(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}

export function formatPopulation(population: number | null): string {
  if (population === null) return "Unknown";
  return population.toLocaleString("en-US");
}

export function formatDateTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export type NetworkStatus = "Stable" | "Watch" | "Alert";

export function networkStatusFor(
  statuses: (SeverityLabel | "NORMAL")[],
): NetworkStatus {
  if (statuses.length === 0) return "Stable";
  return statuses.some((s) => s === "HIGH" || s === "CRITICAL")
    ? "Alert"
    : "Watch";
}

export function formatIncidentType(type: string): string {
  return type
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

export function formatStatusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
}