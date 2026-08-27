import type { StatusTone } from "../lib/presentation";
import { toneClasses } from "../lib/presentation";

interface StatPanelProps {
  label: string;
  value: string;
  note: string;
  tone?: StatusTone;
}

export function StatPanel({ label, value, note, tone }: StatPanelProps) {
  return (
    <div className="panel p-4">
      <p className="label-mono">{label}</p>
      <p
        className={`mt-2 font-mono text-3xl leading-none font-semibold ${
          tone ? toneClasses(tone).split(" ")[1] : "text-foreground"
        }`}
      >
        {value}
      </p>
      <p className="mt-2 text-xs text-muted-foreground">{note}</p>
    </div>
  );
}

interface MiniStatProps {
  label: string;
  value: string;
}

export function MiniStat({ label, value }: MiniStatProps) {
  return (
    <div className="rounded-md border border-border/70 bg-secondary/30 px-3 py-2.5">
      <span className="block text-xs text-muted-foreground">{label}</span>
      <span className="mt-0.5 block font-mono text-sm">{value}</span>
    </div>
  );
}