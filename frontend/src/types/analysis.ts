export type SeverityLabel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type IncidentType =
  | "WATER_LOSS"
  | "PRESSURE_ANOMALY"
  | "WATER_QUALITY"
  | "SUPPLY_DISRUPTION"
  | "UNKNOWN";

export type IncidentStatus =
  | "DETECTED"
  | "INVESTIGATING"
  | "ASSIGNED"
  | "RESOLVED";

export type AnalysisSource = "AI" | "FALLBACK";

export type FallbackReason =
  | "PROVIDER_UNAVAILABLE"
  | "PROVIDER_TIMEOUT"
  | "MALFORMED_RESPONSE"
  | "INVALID_RESPONSE"
  | "PROVIDER_ERROR";

export interface AnalysisRunRequest {
  seed: number;
  days: number;
  scenario?: string | null;
  reference_seed: number;
}

export interface ContributingSignalOut {
  metric: string;
  direction: string;
  anomaly_count: number;
  mean_z: number;
  mean_abs_z: number;
}

export interface IncidentEvidenceOut {
  contributing_signals: ContributingSignalOut[];
  signal_types: string[];
  evidence_score: number;
  temporal_coherence: number;
  spatial_coherence: number;
  signal_diversity: number;
  persistence_minutes: number;
  sensor_anomaly_count: number;
  citizen_report_count: number;
}

export interface DeterministicIncidentOut {
  incident_id: string;
  zone_id: string;
  incident_type: IncidentType;
  status: IncidentStatus;
  severity: SeverityLabel;
  risk_score: number;
  confidence: number;
  start_time: string;
  last_updated: string;
  estimated_affected_population: number | null;
  classification_reason: string;
  explanation: string;
}

export interface AIInfoOut {
  source: AnalysisSource;
  ai_available: boolean;
  fallback_reason: FallbackReason | null;
}

export interface PossibleCause {
  cause: string;
  framing: "possible" | "plausible" | "consistent";
  supporting_evidence: string[];
  notes: string | null;
}

export interface InvestigationAction {
  action: string;
  category: string | null;
  priority: number;
  rationale: string;
}

export interface ResponseOption {
  recommendation: string;
  priority: number | null;
  rationale: string | null;
  advisory: true;
}

export interface Uncertainty {
  supported: string[];
  uncertain: string[];
  additional_information: string[];
}

export interface AIIncidentAnalysis {
  incident_id: string;
  summary: string;
  evidence_interpretation: string;
  possible_causes: PossibleCause[];
  investigation_actions: InvestigationAction[];
  response_options: ResponseOption[];
  uncertainty: Uncertainty;
  safety_notes: string[];
}

export interface AnalysisIncidentOut {
  incident: DeterministicIncidentOut;
  evidence: IncidentEvidenceOut;
  ai: AIInfoOut;
  analysis: AIIncidentAnalysis;
}

export interface AnalysisRunMetadata {
  run_id: string;
  seed: number;
  days: number;
  scenario: string | null;
  reference_seed: number;
  data_source: "deterministic-simulation";
  ran_at: string;
}

export interface AnalysisRunSummary {
  incidents: number;
  ai_source_count: number;
  fallback_count: number;
  zones: number;
  window_hours: number;
}

export interface AnalysisRunResponse {
  run: AnalysisRunMetadata;
  incidents: AnalysisIncidentOut[];
  summary: AnalysisRunSummary;
}

export const DEMO_SCENARIO_ID = "ZONE_B_SUPPLY_INCIDENT";

export const REFERENCE_SEED = 99;
export const DEFAULT_ANALYSIS_DAYS = 1;
export const DEFAULT_SEED = 42;