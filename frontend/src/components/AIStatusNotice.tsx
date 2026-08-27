import type { FallbackReason } from "../types/analysis";

interface AIStatusNoticeProps {
  source: "AI" | "FALLBACK";
  fallbackReason?: FallbackReason | null;
}

export function AIStatusNotice({ source, fallbackReason }: AIStatusNoticeProps) {
  if (source === "FALLBACK") {
    return (
      <div className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2.5 text-xs text-warn">
        <p className="font-mono font-medium tracking-wide">
          AI analysis unavailable — deterministic analysis remains available.
        </p>
        {fallbackReason && (
          <p className="mt-1 font-mono text-[0.68rem] uppercase tracking-wider opacity-80">
            Fallback reason: {fallbackReason}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-md border border-primary/40 bg-primary/10 px-3 py-2.5 text-xs text-primary">
      <p className="font-mono font-medium tracking-wide">AI analysis available.</p>
    </div>
  );
}