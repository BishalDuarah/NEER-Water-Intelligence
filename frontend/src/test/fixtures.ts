import type {
  AnalysisIncidentOut,
  AnalysisRunResponse,
} from "../types/analysis";

function analysisFor(summary: string): AnalysisIncidentOut["analysis"] {
  return {
    incident_id: "INC-B-20260101T060000Z",
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
    incident_id: "INC-B-20260101T060000Z",
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
      { metric: "flow", direction: "above", anomaly_count: 22, mean_z: 8.16, mean_abs_z: 8.16 },
      { metric: "pressure", direction: "below", anomaly_count: 24, mean_z: -32.009, mean_abs_z: 32.009 },
      { metric: "quality", direction: "below", anomaly_count: 20, mean_z: -4.669, mean_abs_z: 4.669 },
      { metric: "consumption", direction: "below", anomaly_count: 23, mean_z: -12.883, mean_abs_z: 12.883 },
    ],
    signal_types: ["consumption", "flow", "pressure", "quality"],
    evidence_score: 0.985,
    temporal_coherence: 1.0,
    spatial_coherence: 1.0,
    signal_diversity: 1.0,
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