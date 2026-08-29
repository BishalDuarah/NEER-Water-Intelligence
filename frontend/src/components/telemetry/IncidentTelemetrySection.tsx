import { useMemo, useState } from "react";
import { useTelemetry } from "../../hooks/useTelemetry";
import type { TelemetryMetric } from "../../types/telemetry";
import { metricLabel, measurementsForSeries, zoneById } from "../../lib/telemetry";
import { TelemetryChart } from "./TelemetryChart";
import { ActivityIcon } from "../icons";

interface IncidentTelemetrySectionProps {
  zoneId: string;
  seed: number;
  days: number;
  scenario: string | null;
}

export function IncidentTelemetrySection({
  zoneId,
  seed,
  days,
  scenario,
}: IncidentTelemetrySectionProps) {
  const { state, run } = useTelemetry();
  const [metric, setMetric] = useState<TelemetryMetric>("pressure");

  const handleLoad = () => {
    void run({ seed, days, scenario });
  };

  const result = state.status === "success" ? state.result : null;
  const zone = result ? zoneById(result.zones, zoneId) : undefined;
  const scenarioForZone = useMemo(
    () => result?.scenarios.find((s) => s.zone_id === zoneId) ?? null,
    [result, zoneId],
  );
  const series = useMemo(
    () =>
      result ? measurementsForSeries(result.measurements, zoneId, metric) : [],
    [result, zoneId, metric],
  );

  return (
    <section className="panel p-5" aria-label="Incident zone telemetry">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="label-mono">Incident zone telemetry</p>
          <h2 className="mt-1 text-sm font-semibold">
            Zone {zoneId} — {metricLabel(metric)}
          </h2>
        </div>
        <button
          type="button"
          onClick={handleLoad}
          disabled={state.status === "loading"}
          className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 bg-secondary text-secondaryForeground hover:brightness-110"
        >
          {state.status === "loading" ? (
            <span
              aria-hidden="true"
              className="size-3 animate-spin rounded-full border-2 border-border border-t-current"
            />
          ) : (
            <ActivityIcon className="size-3.5" />
          )}
          {state.status === "loading"
            ? "Loading…"
            : state.status === "success"
              ? "Rerun"
              : "Load telemetry"}
        </button>
      </div>

      <div className="mt-3">
        <div className="label-mono mb-1.5">Metric</div>
        <div
          className="flex flex-wrap gap-2"
          role="radiogroup"
          aria-label="Select telemetry metric"
        >
          {(["pressure", "flow", "consumption", "quality"] as TelemetryMetric[]).map(
            (m) => (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={metric === m}
                onClick={() => setMetric(m)}
                className={`rounded-md px-3 py-1.5 text-xs transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  metric === m
                    ? "border border-primary/40 bg-primary/15 text-primary"
                    : "border border-border/40 text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`}
              >
                {metricLabel(m)}
              </button>
            ),
          )}
        </div>
      </div>

      {state.status === "idle" && (
        <p className="mt-3 text-xs text-muted-foreground">
          Load the deterministic measurements for this incident's zone to see
          the time series around the incident window.
        </p>
      )}

      {state.status === "error" && (
        <p className="mt-3 text-xs text-destructive" role="alert">
          {state.message}
        </p>
      )}

      {state.status === "success" && result && zone && (
        <div className="mt-3">
          <TelemetryChart
            measurements={result.measurements}
            metric={metric}
            unit={series[0]?.unit ?? metricLabel(metric)}
            windowStart={scenarioForZone?.window_start ?? null}
            windowEnd={scenarioForZone?.window_end ?? null}
            label={`${zone.name} — ${metricLabel(metric)}`}
          />
          {scenarioForZone && (
            <p className="mt-1 text-[0.68rem] text-muted-foreground">
              Incident window from scenario: {scenarioForZone.window_start} →{" "}
              {scenarioForZone.window_end}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
