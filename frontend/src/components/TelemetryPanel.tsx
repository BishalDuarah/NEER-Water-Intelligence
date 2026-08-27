import { ActivityIcon } from "./icons";

export function TelemetryPanel() {
  return (
    <section className="panel p-5" aria-label="Network telemetry">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="label-mono">Sensor telemetry</p>
          <h2 className="mt-1 text-sm font-semibold">Flow &amp; Pressure</h2>
        </div>
        <span className="chip border-border/50 text-muted-foreground">
          Live stream
        </span>
      </div>
      <div className="mt-4 flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border/70 px-4 py-10 text-center">
        <ActivityIcon className="size-6 text-muted-foreground/60" />
        <p className="text-sm text-muted-foreground">
          Raw telemetry time-series is not part of this API phase.
        </p>
        <p className="max-w-sm text-xs text-muted-foreground/70">
          The analysis pipeline returns deterministic incident evidence
          summaries instead of continuous sensor streams. Time-series
          visualization arrives with the water-network telemetry phase.
        </p>
      </div>
    </section>
  );
}