import type {
  AnalysisIncidentOut,
  AnalysisRunResponse,
} from "../types/analysis";

function analysisFor(summary: string): AnalysisIncidentOut["analysis"] {
  return {
    incident_id: "INC-ZB-000042",
    summary,
    evidence_interpretation:
      "Flow, pressure, quality and consumption signals deviate together within a short window, and citizen reports rise in the same period — characteristic of a supply-side disturbance in one zone.",
    possible_causes: [
      {
        cause: "Burst or significant leak on a transmission line feeding Zone B",
        framing: "plausible",
        supporting_evidence: ["Sustained pressure drop", "Above-baseline flow"],
        notes: null,
      },
    ],
    investigation_actions: [
      {
        action: "Confirm isolation valve positions at the Zone B district meter",
        category: "field verification",
        priority: 80,
        rationale: "Narrow the physical boundary of the suspected loss.",
      },
    ],
    response_options: [
      {
        recommendation: "Prepare for planned supply isolation under operator command",
        priority: 70,
        rationale: "Only an operator may act; the platform never controls valves.",
        advisory: true,
      },
    ],
    uncertainty: {
      supported: ["Pressure drop", "Elevated flow", "Rising complaints"],
      uncertain: ["Exact leak location", "Leak magnitude"],
      additional_information: ["SCADA alarm logs for the district meter"],
    },
    safety_notes: [
      "No autonomous action. All recommendations require human operator approval.",
    ],
  };
}

export const goldenIncident: AnalysisIncidentOut = {
  incident: {
    incident_id: "INC-ZB-000042",
    zone_id: "B",
    incident_type: "WATER_LOSS",
    status: "DETECTED",
    severity: "CRITICAL",
    risk_score: 91.52,
    confidence: 0.9918,
    start_time: "2026-08-28T06:00:00Z",
    last_updated: "2026-08-28T06:30:00Z",
    estimated_affected_population: 32000,
    classification_reason:
      "Combined pressure, flow, consumption and quality anomalies with rising citizen reports exceed the correlation trigger for a supply interruption.",
    explanation:
      "Abnormal flow and a sustained pressure drop coincide with a spike in customer complaints, consistent with a supply-side water loss in Zone B.",
  },
  evidence: {
    contributing_signals: [
      { metric: "flow", direction: "above_baseline", anomaly_count: 22, mean_z: 3.02, mean_abs_z: 3.02 },
      { metric: "pressure", direction: "below_baseline", anomaly_count: 27, mean_z: -2.91, mean_abs_z: 2.91 },
      { metric: "quality", direction: "abnormal", anomaly_count: 17, mean_z: 2.66, mean_abs_z: 2.66 },
      { metric: "consumption", direction: "above_baseline", anomaly_count: 23, mean_z: 2.41, mean_abs_z: 2.41 },
    ],
    signal_types: ["flow", "pressure", "quality", "consumption"],
    evidence_score: 0.985,
    temporal_coherence: 0.94,
    spatial_coherence: 0.91,
    signal_diversity: 0.8,
    persistence_minutes: 345,
    sensor_anomaly_count: 89,
    citizen_report_count: 12,
  },
  ai: { source: "FALLBACK", ai_available: false, fallback_reason: "PROVIDER_UNAVAILABLE" },
  analysis: analysisFor(
    "Evidence pattern points to a likely supply-side water loss in Zone B; verify pressure and flow at the district meter before escalation.",
  ),
};

export const goldenResponse: AnalysisRunResponse = {
  run: {
    run_id: "run-42-1-99-ZONE_B_SUPPLY_INCIDENT",
    seed: 42,
    days: 1,
    scenario: "ZONE_B_SUPPLY_INCIDENT",
    reference_seed: 99,
    data_source: "deterministic-simulation",
    ran_at: "2026-08-28T09:00:00Z",
  },
  incidents: [goldenIncident],
  summary: {
    incidents: 1,
    ai_source_count: 0,
    fallback_count: 1,
    zones: 4,
    window_hours: 168,
  },
};

export const aiResponse: AnalysisRunResponse = {
  run: { ...goldenResponse.run },
  incidents: [
    {
      ...goldenIncident,
      ai: { source: "AI", ai_available: true, fallback_reason: null },
      analysis: analysisFor(
        "Cross-zone evidence supports a water loss; recommend operator inspection of the Zone B distribution inlet.",
      ),
    },
  ],
  summary: { incidents: 1, ai_source_count: 1, fallback_count: 0, zones: 4, window_hours: 168 },
};

export const normalResponse: AnalysisRunResponse = {
  run: {
    run_id: "run-42-1-99-normal",
    seed: 42,
    days: 1,
    scenario: null,
    reference_seed: 99,
    data_source: "deterministic-simulation",
    ran_at: "2026-08-28T09:05:00Z",
  },
  incidents: [],
  summary: { incidents: 0, ai_source_count: 0, fallback_count: 0, zones: 4, window_hours: 168 },
};