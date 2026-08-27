import { networkStatusFor } from "../lib/presentation";
import { toneClasses } from "../lib/presentation";
import type { StatusTone } from "../lib/presentation";

const TONES: Record<"Stable" | "Watch" | "Alert", StatusTone> = {
  Stable: "ok",
  Watch: "warn",
  Alert: "danger",
};

export function NetworkStatusPill({
  status,
}: {
  status: "Stable" | "Watch" | "Alert";
}) {
  const tone = TONES[status];
  return (
    <span className={`chip ${toneClasses(tone)}`} role="status">
      <span aria-hidden="true" className="size-2 rounded-full bg-current" />
      Network Status: {status}
    </span>
  );
}

export { networkStatusFor };