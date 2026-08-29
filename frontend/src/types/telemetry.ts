export type TelemetryMetric =
  | "flow"
  | "pressure"
  | "quality"
  | "consumption";

export interface TelemetryRunRequest {
  seed: number;
  days: number;
  scenario?: string | null;
}

export interface TelemetryZone {
  zone_id: string;
  name: string;
  district: string;
  area_sq_km: number;
  estimated_population: number;
}

export interface TelemetryMeasurement {
  timestamp: string;
  zone_id: string;
  metric: TelemetryMetric;
  value: number;
  unit: string;
}

export interface TelemetryScenario {
  scenario_id: string;
  zone_id: string;
  window_start: string;
  window_end: string;
  description: string;
}

export interface TelemetryRunMetadata {
  run_id: string;
  seed: number;
  days: number;
  scenario: string | null;
  data_source: "deterministic-simulation";
  window_hours: number;
  zone_count: number;
  measurement_count: number;
  ran_at: string;
}

export interface TelemetryRunResponse {
  run: TelemetryRunMetadata;
  zones: TelemetryZone[];
  measurements: TelemetryMeasurement[];
  scenarios: TelemetryScenario[];
}

export const TELEMETRY_METRICS: TelemetryMetric[] = [
  "flow",
  "pressure",
  "quality",
  "consumption",
];

export const DEFAULT_TELEMETRY_DAYS = 1;
export const DEFAULT_TELEMETRY_SEED = 42;
