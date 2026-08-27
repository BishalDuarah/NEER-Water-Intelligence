export function IdlePanel() {
  return (
    <div className="panel flex items-center gap-3 px-4 py-8 text-sm text-muted-foreground">
      <span aria-hidden="true" className="size-2 rounded-full bg-ok" />
      No analysis has been run yet. Use the simulation engine to analyze the
      water network for this scenario.
    </div>
  );
}

export function LoadingPanel() {
  return (
    <div
      className="panel flex items-center justify-center gap-3 px-4 py-8 text-sm text-muted-foreground"
      role="status"
    >
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-border border-t-primary"
      />
      Running deterministic analysis pipeline…
    </div>
  );
}

export function EmptyIncidentsPanel() {
  return (
    <div className="flex items-center gap-3 rounded-md border border-border/70 bg-secondary/30 px-4 py-8 text-sm text-muted-foreground">
      <span aria-hidden="true" className="size-2 rounded-full bg-ok" />
      No active incidents. Network signals nominal across all monitored zones.
    </div>
  );
}

interface ErrorPanelProps {
  message: string;
  onRetry: () => void;
}

export function ErrorPanel({ message, onRetry }: ErrorPanelProps) {
  return (
    <div
      className="panel border-destructive/50 px-5 py-6 text-sm"
      role="alert"
    >
      <p className="font-semibold text-destructive">Analysis failed.</p>
      <p className="mt-1 text-muted-foreground">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-4 inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring bg-secondary text-secondaryForeground hover:brightness-110"
      >
        Try again
      </button>
    </div>
  );
}