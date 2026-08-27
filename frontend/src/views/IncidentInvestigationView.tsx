import type { ReactNode } from "react";
import { AIStatusNotice } from "../components/AIStatusNotice";
import { SeverityChip } from "../components/SeverityChip";
import { ArrowRightIcon } from "../components/icons";
import {
  directionIndicator,
  formatConfidencePair,
  formatDateTime,
  formatDuration,
  formatPopulation,
  formatRisk,
} from "../lib/presentation";
import type { AnalysisIncidentOut, PossibleCause } from "../types/analysis";

interface IncidentInvestigationViewProps {
  incident: AnalysisIncidentOut | null;
  onBack: () => void;
}

function PanelHeader({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div>
        <p className="label-mono">{kicker}</p>
        <h2 className="mt-1 text-sm font-semibold">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2.5">
      <span className="block text-xs text-muted-foreground">{label}</span>
      <span className="mt-0.5 block font-mono text-sm font-medium">{value}</span>
      {note && (
        <span className="mt-0.5 block text-[0.68rem] text-muted-foreground/80">
          {note}
        </span>
      )}
    </div>
  );
}

function EmptyInvestigation({ onBack }: { onBack: () => void }) {
  return (
    <div
      className="panel flex flex-col items-center gap-2 px-4 py-10 text-center"
      data-testid="investigation-empty"
    >
      <p className="text-sm font-semibold">
        No incidents available for investigation.
      </p>
      <p className="max-w-sm text-xs text-muted-foreground">
        Run an analysis with a detected incident to inspect evidence.
      </p>
      <button
        type="button"
        onClick={onBack}
        className="mt-2 inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring bg-secondary text-secondaryForeground hover:brightness-110"
      >
        <ArrowRightIcon className="size-4 -scale-x-100" />
        Back to Operations
      </button>
    </div>
  );
}

function PossibleCauseCard({ cause }: { cause: PossibleCause }) {
  return (
    <li className="rounded-md border border-border/70 bg-secondary/30 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium">{cause.cause}</p>
        <span className="chip border-border/50 text-muted-foreground">
          {cause.framing}
        </span>
      </div>
      {cause.supporting_evidence.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {cause.supporting_evidence.map((evidence, index) => (
            <li
              key={index}
              className="chip border-border/40 bg-secondary/40 text-muted-foreground"
            >
              {evidence}
            </li>
          ))}
        </ul>
      )}
      {cause.notes && (
        <p className="mt-2 text-xs text-muted-foreground">{cause.notes}</p>
      )}
    </li>
  );
}

export function IncidentInvestigationView({
  incident,
  onBack,
}: IncidentInvestigationViewProps) {
  if (incident === null) {
    return (
      <div className="flex flex-col gap-4">
        <header>
          <p className="label-mono">Incident investigation</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            Incident Investigation
          </h1>
        </header>
        <EmptyInvestigation onBack={onBack} />
      </div>
    );
  }

  const { incident: record, evidence, ai, analysis } = incident;
  const isAi = ai.source === "AI";
  const assessmentConfidence = `${(record.confidence * 100).toFixed(2)}%`;
  const hierarchy = `ZONE ${record.zone_id} / ${record.incident_type.replace(/_/g, " ")} / ${record.severity}`;

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <div>
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <ArrowRightIcon className="size-4 -scale-x-100" />
          Back to Operations
        </button>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label-mono">Incident investigation</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            Incident Investigation
          </h1>
        </div>
        <SeverityChip status={record.severity} label={record.severity} />
      </header>

      <p className="rounded-md border border-border/60 bg-secondary/20 px-4 py-3 text-xs text-muted-foreground">
        <span className="font-mono font-medium text-foreground/80">
          Decision support only.
        </span>{" "}
        NEER provides evidence-based analysis and advisory recommendations. No
        infrastructure action is executed by this interface.
      </p>

      <section className="panel p-5" aria-label="Incident summary">
        <PanelHeader kicker="Incident record" title="Incident Header" />
        <p className="mt-3 font-mono text-base font-semibold uppercase tracking-wide">
          {hierarchy}
        </p>
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-6">
          <Metric label="Incident ID" value={record.incident_id} />
          <Metric label="Zone" value={`Zone ${record.zone_id}`} />
          <Metric
            label="Type"
            value={record.incident_type.replace(/_/g, " ")}
          />
          <Metric label="Status" value={record.status} />
          <Metric
            label="Detected"
            value={formatDateTime(record.start_time)}
            note="start_time"
          />
          <Metric
            label="Last updated"
            value={formatDateTime(record.last_updated)}
            note="last_updated"
          />
        </div>
      </section>

      <section
        className="panel p-5"
        aria-label="Risk and assessment"
        data-testid="investigation-risk"
      >
        <PanelHeader kicker="Deterministic assessment" title="Risk & Assessment" />
        <div className="mt-3 rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3">
          <p className="label-mono text-destructive">Risk score</p>
          <p className="mt-1 font-mono text-3xl leading-none font-semibold text-destructive">
            {formatRisk(record.risk_score)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Weighted deterministic risk, scaled 0–100.
          </p>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-6">
          <Metric
            label="Confidence"
            value={formatConfidencePair(record.confidence)}
            note="decimal / percent"
          />
          <Metric
            label="Evidence score"
            value={evidence.evidence_score.toFixed(3)}
            note="correlation strength"
          />
          <Metric
            label="Persistence"
            value={formatDuration(evidence.persistence_minutes)}
            note={`${evidence.persistence_minutes} minutes`}
          />
          <Metric
            label="Affected population"
            value={formatPopulation(record.estimated_affected_population)}
          />
          <Metric
            label="Citizen reports"
            value={String(evidence.citizen_report_count)}
          />
          <Metric
            label="Sensor anomalies"
            value={String(evidence.sensor_anomaly_count)}
          />
        </div>
      </section>

      <section
        className="panel p-5"
        aria-label="Signal evidence"
        data-testid="investigation-signals"
      >
        <PanelHeader kicker="Sensor evidence" title="Contributing Signals" />
        <p className="mt-1 text-xs text-muted-foreground">
          Direction and statistics come from the deterministic pipeline; this
          view never infers signal behavior.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[480px] border-collapse text-left">
            <thead>
              <tr className="border-b border-border/70 text-[0.68rem] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Metric</th>
                <th className="py-2 pr-3 font-medium">Direction</th>
                <th className="py-2 pr-3 text-right font-medium">Anomalies</th>
                <th className="py-2 pr-3 text-right font-medium">Mean z</th>
                <th className="py-2 text-right font-medium">Mean |z|</th>
              </tr>
            </thead>
            <tbody>
              {evidence.contributing_signals.map((signal) => (
                <tr
                  key={signal.metric}
                  className="border-b border-border/40 font-mono text-sm"
                >
                  <td className="py-2 pr-3">{signal.metric}</td>
                  <td className="py-2 pr-3">
                    <span className="mr-1">{directionIndicator(signal.direction)}</span>
                    <span className="text-muted-foreground">
                      {signal.direction}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-right">
                    {signal.anomaly_count}
                  </td>
                  <td className="py-2 pr-3 text-right">
                    {signal.mean_z.toFixed(2)}
                  </td>
                  <td className="py-2 text-right">
                    {signal.mean_abs_z.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section
        className="panel p-5"
        aria-label="Correlated evidence"
        data-testid="investigation-correlation"
      >
        <PanelHeader kicker="Cross-signal correlation" title="Correlated Evidence" />
        <p className="mt-3 rounded-md border border-border/60 bg-secondary/30 px-3 py-2 text-sm">
          Multiple independent signals were observed together over time.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-6">
          <Metric
            label="Evidence score"
            value={evidence.evidence_score.toFixed(3)}
          />
          <Metric
            label="Temporal coherence"
            value={evidence.temporal_coherence.toFixed(2)}
          />
          <Metric
            label="Spatial coherence"
            value={evidence.spatial_coherence.toFixed(2)}
          />
          <Metric
            label="Signal diversity"
            value={evidence.signal_diversity.toFixed(2)}
          />
          <Metric
            label="Persistence"
            value={formatDuration(evidence.persistence_minutes)}
            note={`${evidence.persistence_minutes} minutes`}
          />
          <Metric
            label="Sensor anomalies"
            value={String(evidence.sensor_anomaly_count)}
          />
        </div>
        <div className="mt-3 rounded-md border border-border/70 bg-background/40 px-3 py-2">
          <p className="label-mono">Classification</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {record.classification_reason}
          </p>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {record.explanation}
        </p>
      </section>

      <section className="panel p-5" aria-label="Citizen reports">
        <PanelHeader
          kicker="Crowd-sourced context"
          title="Citizen Reports"
        />
        {evidence.citizen_report_count === 0 ? (
          <p className="mt-3 text-xs text-muted-foreground">
            No citizen reports are associated with this incident.
          </p>
        ) : (
          <>
            <p className="mt-3 font-mono text-sm">
              {evidence.citizen_report_count} reports counted in incident
              evidence for zone {record.zone_id}.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Aggregated counts only — individual reports, locations and
              personal details are not stored or displayed.
            </p>
          </>
        )}
      </section>

      <section
        className="panel p-5"
        aria-label="AI incident analysis"
        data-testid="investigation-analysis"
      >
        <PanelHeader
          kicker="Intelligence analysis"
          title={
            isAi ? "AI Incident Analysis" : "Incident Analysis (Deterministic Fallback)"
          }
        >
          {isAi ? (
            <span className="chip border-primary/40 bg-primary/15 text-primary">
              AI-assisted interpretation
            </span>
          ) : (
            <span className="chip border-warn/40 bg-warn/15 text-warn">
              Deterministic fallback analysis
            </span>
          )}
        </PanelHeader>

        <div className="mt-3">
          <AIStatusNotice source={ai.source} fallbackReason={ai.fallback_reason} />
        </div>

        <div className="mt-3 rounded-md border border-border/70 bg-background/40 px-3 py-2">
          <p className="label-mono">Summary</p>
          <p className="mt-1 text-xs text-muted-foreground">{analysis.summary}</p>
        </div>

        <div className="mt-3 rounded-md border border-border/70 bg-background/40 px-3 py-2">
          <p className="label-mono">Evidence interpretation</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {analysis.evidence_interpretation}
          </p>
        </div>

        {analysis.possible_causes.length > 0 && (
          <div className="mt-4">
            <p className="label-mono">Possible causes</p>
            <ul className="mt-2 flex flex-col gap-2">
              {analysis.possible_causes.map((cause, index) => (
                <PossibleCauseCard key={index} cause={cause} />
              ))}
            </ul>
          </div>
        )}

        {analysis.investigation_actions.length > 0 && (
          <div className="mt-4">
            <p className="label-mono">Suggested investigation</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Suggested steps for an operator to verify — nothing is executed
              by this platform.
            </p>
            <ul className="mt-2 flex flex-col gap-2">
              {analysis.investigation_actions.map((action, index) => (
                <li
                  key={index}
                  className="rounded-md border border-border/70 bg-secondary/30 p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-medium">{action.action}</p>
                    <span className="chip border-border/50 text-muted-foreground">
                      Priority {action.priority}
                    </span>
                  </div>
                  {action.category && (
                    <p className="mt-1 text-xs uppercase tracking-wider text-muted-foreground">
                      {action.category}
                    </p>
                  )}
                  <p className="mt-1 text-xs text-muted-foreground">
                    {action.rationale}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}

        {analysis.response_options.length > 0 && (
          <div className="mt-4">
            <p className="label-mono">Advisory response options</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Operator decision required. These are suggestions, not commands.
            </p>
            <ul className="mt-2 flex flex-col gap-2">
              {analysis.response_options.map((option, index) => (
                <li
                  key={index}
                  className="rounded-md border border-border/70 bg-secondary/30 p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-medium">{option.recommendation}</p>
                    <span className="chip border-border/50 text-muted-foreground">
                      Advisory
                    </span>
                  </div>
                  {option.priority !== null && (
                    <p className="mt-1 text-xs uppercase tracking-wider text-muted-foreground">
                      Priority {option.priority}
                    </p>
                  )}
                  {option.rationale && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {option.rationale}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-4">
          <p className="label-mono">Uncertainty</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Assessment confidence: {assessmentConfidence} — confidence describes
            how strongly the deterministic evidence fits the classification,
            not the probability of a specific physical cause.
          </p>
          <div className="mt-2 grid gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2.5">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Supported
              </p>
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {analysis.uncertainty.supported.length === 0 ? (
                  <li className="text-xs text-muted-foreground">None</li>
                ) : (
                  analysis.uncertainty.supported.map((item, index) => (
                    <li
                      key={index}
                      className="chip border-border/40 bg-background/40 text-muted-foreground"
                    >
                      {item}
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2.5">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Uncertain
              </p>
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {analysis.uncertainty.uncertain.length === 0 ? (
                  <li className="text-xs text-muted-foreground">None</li>
                ) : (
                  analysis.uncertainty.uncertain.map((item, index) => (
                    <li
                      key={index}
                      className="chip border-border/40 bg-background/40 text-muted-foreground"
                    >
                      {item}
                    </li>
                  ))
                )}
              </ul>
            </div>
            <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2.5">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Further information
              </p>
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {analysis.uncertainty.additional_information.length === 0 ? (
                  <li className="text-xs text-muted-foreground">None</li>
                ) : (
                  analysis.uncertainty.additional_information.map((item, index) => (
                    <li
                      key={index}
                      className="chip border-border/40 bg-background/40 text-muted-foreground"
                    >
                      {item}
                    </li>
                  ))
                )}
              </ul>
            </div>
          </div>
        </div>

        {analysis.safety_notes.length > 0 && (
          <div className="mt-4">
            <p className="label-mono">Safety</p>
            <ul className="mt-2 flex flex-col gap-1.5">
              {analysis.safety_notes.map((note, index) => (
                <li key={index} className="text-xs text-muted-foreground">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}