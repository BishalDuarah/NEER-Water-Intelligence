import { useMemo, useState } from "react";
import { useTelemetry } from "../hooks/useTelemetry";
import {
  DEFAULT_TELEMETRY_DAYS,
  DEFAULT_TELEMETRY_SEED,
} from "../types/telemetry";
import type { TelemetryMetric } from "../types/telemetry";
import { metricLabel, measurementsForSeries, zoneById } from "../lib/telemetry";
import { TelemetryChart } from "./telemetry/TelemetryChart";
import { TelemetryControls } from "./telemetry/TelemetryControls";
import { ActivityIcon } from "./icons";

interface TelemetryPanelProps {
  scenario?: string | null;
  seed?: number;
  days?: number;
  title?: string;
}

export function TelemetryPanel({
  scenario = null,
  seed = DEFAULT_TELEMETRY_SEED,
  days = DEFAULT_TELEMETRY_DAYS,
  title = "Flow & Pressure",
}: TelemetryPanelProps) {
  const { state, run } = useTelemetry();
  const [selectedZone, setSelectedZone] = useState<string>("B");
  const [selectedMetric, setSelectedMetric] =
    useState<TelemetryMetric>("pressure");

  const handleRun = () => {
    void run({ seed, days, scenario });
  };

  const result = state.status === "success" ? state.result : null;

  const zones = result?.zones ?? [];
  const activeZone = zones.length > 0 ? selectedZone : "";
  const activeZoneValid = activeZone !== "" && zoneById(zones, activeZone) != null;

  const seriesMeasurements = useMemo(
    () =>
      result && activeZoneValid
        ? measurementsForSeries(result.measurements, activeZone, selectedMetric)
        : [],
    [result, activeZone, activeZoneValid, selectedMetric],
  );

  const scenarioForZone = useMemo(
    () =>
      result?.scenarios.find((s) => s.zone_id === activeZone) ?? null,
    [result, activeZone],
  );

  const zoneObj = activeZone ? zoneById(zones, activeZone) : undefined;

  return (
    <section className="panel p-5" aria-label="Network telemetry">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="label-mono">Sensor telemetry</p>
          <h2 className="mt-1 text-sm font-semibold">{title}</h2>
        </div>
        <span className="chip border-border/50 text-muted-foreground">
          Deterministic
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
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
          {state.status === "loading"
            ? "Running…"
            : state.status === "success"
              ? "Rerun telemetry"
              : "Load telemetry"}
        </button>
        {state.status === "success" && result && (
          <span className="chip border-ok/40 bg-ok/15 text-ok">
            {result.measurements.length.toLocaleString("en-US")} samples
          </span>
        )}
        {state.status === "success" && result && result.scenarios.length > 0 && (
          <span className="chip border-warn/40 bg-warn/15 text-warn">
            Incident window
          </span>
        )}
      </div>

      {state.status === "idle" && (
        <div className="mt-4 flex items-center gap-2 rounded-md border border-dashed border-border/70 px-4 py-6 text-sm text-muted-foreground">
          <ActivityIcon className="size-5 text-muted-foreground/60" />
          Load the deterministic telemetry series for this network to render
          live charts.
        </div>
      )}

      {state.status === "error" && (
        <div
          className="mt-4 rounded-md border border-destructive/50 px-4 py-3 text-sm"
          role="alert"
        >
          <p className="font-semibold text-destructive">Telemetry failed.</p>
          <p className="mt-1 text-muted-foreground">{state.message}</p>
        </div>
      )}

      {state.status === "success" && result && (
        <div className="mt-4">
          <TelemetryControls
            zones={result.zones}
            selectedZone={activeZone}
            onZoneChange={setSelectedZone}
            selectedMetric={selectedMetric}
            onMetricChange={setSelectedMetric}
          />
          <div className="mt-4">
            <TelemetryChart
              measurements={result.measurements}
              metric={selectedMetric}
              unit={
                seriesMeasurements[0]?.unit ??
                metricLabel(selectedMetric)
              }
              windowStart={scenarioForZone?.window_start ?? null}
              windowEnd={scenarioForZone?.window_end ?? null}
              label={`${zoneObj?.name ?? activeZone} — ${metricLabel(
                selectedMetric,
              )}`}
            />
          </div>
        </div>
      )}
    </section>
  );
}
