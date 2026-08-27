import {
  formatConfidencePercent,
  formatDuration,
  formatIncidentType,
  formatPopulation,
  formatRisk,
  toneClasses,
  toneFor,
} from "../lib/presentation";
import type { AnalysisIncidentOut } from "../types/analysis";
import { AIStatusNotice } from "./AIStatusNotice";
import { SeverityChip } from "./SeverityChip";

interface IncidentRowProps {
  item: AnalysisIncidentOut;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label-mono">{label}</p>
      <p className="mt-1 font-mono text-base leading-none">{value}</p>
    </div>
  );
}

export function IncidentRow({ item }: IncidentRowProps) {
  const { incident, evidence } = item;

  return (
    <article className="rounded-md border border-border/70 bg-secondary/30 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">
              Zone {incident.zone_id} · {formatIncidentType(incident.incident_type)}
            </h3>
            <SeverityChip status={incident.severity} label={incident.severity} />
            <span
              className={`chip ${toneClasses(toneFor(incident.severity))}`}
            >
              {incident.status}
            </span>
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {incident.incident_id}
          </p>
        </div>
        <span className="chip border-border/50 text-muted-foreground">
          Risk {formatRisk(incident.risk_score)}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 lg:grid-cols-6">
        <Metric label="Risk" value={formatRisk(incident.risk_score)} />
        <Metric
          label="Confidence"
          value={formatConfidencePercent(incident.confidence)}
        />
        <Metric label="Evidence" value={evidence.evidence_score.toFixed(3)} />
        <Metric
          label="Persistence"
          value={formatDuration(evidence.persistence_minutes)}
        />
        <Metric
          label="Impact"
          value={formatPopulation(incident.estimated_affected_population)}
        />
        <Metric
          label="Anomalies"
          value={String(evidence.sensor_anomaly_count)}
        />
      </div>

      <p className="mt-3 text-xs text-muted-foreground">{incident.explanation}</p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {evidence.contributing_signals.map((signal) => (
          <span
            key={signal.metric}
            className="chip border-border/40 bg-secondary/40 text-muted-foreground"
          >
            {signal.metric} · {signal.direction}
          </span>
        ))}
        <span className="chip border-border/40 text-muted-foreground">
          {evidence.citizen_report_count} reports
        </span>
      </div>

      <div className="mt-4">
        <AIStatusNotice source={item.ai.source} fallbackReason={item.ai.fallback_reason} />
        <div className="mt-2 rounded-md border border-border/70 bg-background/40 px-3 py-2">
          <p className="label-mono">Response suggestion</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {item.analysis.summary}
          </p>
        </div>
      </div>
    </article>
  );
}