import type { ReactNode } from "react";
import type { TelemetryMetric, TelemetryZone } from "../../types/telemetry";
import { TELEMETRY_METRICS } from "../../types/telemetry";
import { metricLabel } from "../../lib/telemetry";

interface TelemetryControlsProps {
  zones: TelemetryZone[];
  selectedZone: string;
  onZoneChange: (zoneId: string) => void;
  selectedMetric: TelemetryMetric;
  onMetricChange: (metric: TelemetryMetric) => void;
}

function OptionButton({
  active,
  onClick,
  children,
  group,
  value,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  group: string;
  value: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      role="radio"
      aria-checked={active}
      aria-label={`${group}: ${value}`}
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
        active
          ? "border border-primary/40 bg-primary/15 text-primary"
          : "border border-border/40 text-muted-foreground hover:bg-secondary hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

export function TelemetryControls({
  zones,
  selectedZone,
  onZoneChange,
  selectedMetric,
  onMetricChange,
}: TelemetryControlsProps) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="label-mono mb-1.5">Zone</p>
        <div
          className="flex flex-wrap gap-2"
          role="radiogroup"
          aria-label="Select zone"
        >
          {zones.map((zone) => (
            <OptionButton
              key={zone.zone_id}
              active={selectedZone === zone.zone_id}
              onClick={() => onZoneChange(zone.zone_id)}
              group="Zone"
              value={zone.name}
            >
              {zone.name}
            </OptionButton>
          ))}
        </div>
      </div>
      <div>
        <p className="label-mono mb-1.5">Metric</p>
        <div
          className="flex flex-wrap gap-2"
          role="radiogroup"
          aria-label="Select metric"
        >
          {TELEMETRY_METRICS.map((metric) => (
            <OptionButton
              key={metric}
              active={selectedMetric === metric}
              onClick={() => onMetricChange(metric)}
              group="Metric"
              value={metricLabel(metric)}
            >
              {metricLabel(metric)}
            </OptionButton>
          ))}
        </div>
      </div>
    </div>
  );
}
