import { ActivityIcon } from "../components/icons";

export function NetworkView() {
  return (
    <div className="flex flex-col gap-4">
      <header>
        <p className="label-mono">Water network</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight">
          Zone Telemetry
        </h1>
      </header>
      <div className="panel flex flex-col items-center justify-center gap-2 px-4 py-10 text-center">
        <ActivityIcon className="size-6 text-muted-foreground/60" />
        <p className="text-sm text-muted-foreground">
          Per-zone time-series telemetry is a later phase.
        </p>
        <p className="max-w-sm text-xs text-muted-foreground/70">
          The analysis API returns deterministic evidence summaries, not raw
          sensor streams. This view will surface zone-level charts once the
          telemetry endpoints exist.
        </p>
      </div>
    </div>
  );
}