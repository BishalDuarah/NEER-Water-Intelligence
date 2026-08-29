import { useEffect, useMemo, useState } from "react";
import { useTelemetry } from "../hooks/useTelemetry";
import {
  DEFAULT_TELEMETRY_DAYS,
  DEFAULT_TELEMETRY_SEED,
} from "../types/telemetry";
import type { TelemetryMetric } from "../types/telemetry";
import { DEMO_SCENARIO_ID } from "../types/analysis";
import { metricLabel, zoneById } from "../lib/telemetry";
import { TelemetryChart } from "../components/telemetry/TelemetryChart";
import { TelemetryControls } from "../components/telemetry/TelemetryControls";
import { ActivityIcon } from "../components/icons";

function ScenarioButton({
  label,
  selected,
  onClick,
}: {
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        selected
          ? "border border-primary/40 bg-primary/15 text-primary"
          : "border border-border/40 text-muted-foreground hover:bg-secondary hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
}

export function NetworkView() {
  const { state, run } = useTelemetry();
  const [scenario, setScenario] = useState<string | null>(null);
  const [selectedZone, setSelectedZone] = useState<string>("B");
  const [selectedMetric, setSelectedMetric] =
    useState<TelemetryMetric>("pressure");

  useEffect(() => {
    void run({
      seed: DEFAULT_TELEMETRY_SEED,
      days: DEFAULT_TELEMETRY_DAYS,
      scenario: null,
    });
  }, [run]);

  const handleRun = () => {
    void run({
      seed: DEFAULT_TELEMETRY_SEED,
      days: DEFAULT_TELEMETRY_DAYS,
      scenario,
    });
  };

  const result = state.status === "success" ? state.result : null;

  const scenarioForZone = useMemo(
    () => result?.scenarios.find((s) => s.zone_id === selectedZone) ?? null,
    [result, selectedZone],
  );

  return (
    <div className="flex flex-col gap-4" aria-live="polite">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="label-mono">Water network</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            Zone Telemetry
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Deterministic simulation measurements — not a live feed.
          </p>
        </div>
        <span className="chip border-border/50 text-muted-foreground">
          Read-only
        </span>
      </header>

      <section className="panel p-5" aria-label="Telemetry run controls">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="label-mono">Simulation run</p>
            <div
              className="mt-2 flex flex-wrap items-center gap-2"
              role="radiogroup"
              aria-label="Choose scenario"
            >
              <ScenarioButton
                label="Normal operation"
                selected={scenario === null}
                onClick={() => setScenario(null)}
              />
              <ScenarioButton
                label={DEMO_SCENARIO_ID}
                selected={scenario === DEMO_SCENARIO_ID}
                onClick={() => setScenario(DEMO_SCENARIO_ID)}
              />
            </div>
          </div>
          <button
            type="button"
            onClick={handleRun}
            disabled={state.status === "loading"}
            className="inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 bg-secondary text-secondaryForeground hover:brightness-110"
          >
            {state.status === "loading" ? (
              <span
                aria-hidden="true"
                className="size-3.5 animate-spin rounded-full border-2 border-border border-t-current"
              />
            ) : (
              <ActivityIcon className="size-4" />
            )}
            {state.status === "loading" ? "Running…" : "Run telemetry"}
          </button>
        </div>
      </section>

      {state.status === "idle" && (
        <div className="panel flex items-center gap-3 px-4 py-8 text-sm text-muted-foreground">
          <ActivityIcon className="size-5 text-muted-foreground/60" />
          Telemetry has not been generated for this view yet.
        </div>
      )}

      {state.status === "error" && (
        <div
          className="panel border-destructive/50 px-5 py-6 text-sm"
          role="alert"
        >
          <p className="font-semibold text-destructive">Telemetry failed.</p>
          <p className="mt-1 text-muted-foreground">{state.message}</p>
        </div>
      )}

      {state.status === "success" && result && (
        <>
          <TelemetryControls
            zones={result.zones}
            selectedZone={selectedZone}
            onZoneChange={setSelectedZone}
            selectedMetric={selectedMetric}
            onMetricChange={setSelectedMetric}
          />

          {scenarioForZone && (
            <div className="rounded-md border border-warn/40 bg-warn/10 px-4 py-2 text-xs text-warn">
              Incident window for {zoneById(result.zones, scenarioForZone.zone_id)?.name}:{" "}
              {scenarioForZone.window_start} → {scenarioForZone.window_end}
            </div>
          )}

          <section
            className="grid gap-4 sm:grid-cols-2"
            aria-label="Telemetry chart grid"
          >
            {result.zones.map((zone) => {
              const scenario = result.scenarios.find(
                (s) => s.zone_id === zone.zone_id,
              );
              const series = result.measurements.filter(
                (m) => m.zone_id === zone.zone_id && m.metric === selectedMetric,
              );
              return (
                <div key={zone.zone_id} className="panel p-4">
                  <TelemetryChart
                    measurements={result.measurements}
                    metric={selectedMetric}
                    unit={series[0]?.unit ?? metricLabel(selectedMetric)}
                    windowStart={scenario?.window_start ?? null}
                    windowEnd={scenario?.window_end ?? null}
                    label={`${zone.name} — ${metricLabel(selectedMetric)}`}
                  />
                </div>
              );
            })}
          </section>
        </>
      )}
    </div>
  );
}
