import { toneClasses, toneFor } from "../lib/presentation";
import type { ZoneStatus } from "../lib/presentation";

interface SeverityChipProps {
  status: ZoneStatus;
  label?: string;
}

export function SeverityChip({ status, label }: SeverityChipProps) {
  return (
    <span className={`chip ${toneClasses(toneFor(status))}`}>
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      {label ?? status}
    </span>
  );
}