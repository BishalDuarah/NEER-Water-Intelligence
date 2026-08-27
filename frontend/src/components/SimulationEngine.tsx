import { useState } from "react";
import {
  DEFAULT_ANALYSIS_DAYS,
  DEFAULT_SEED,
  DEMO_SCENARIO_ID,
  REFERENCE_SEED,
} from "../types/analysis";
import type { AnalysisRunRequest } from "../types/analysis";
import { PlayIcon } from "./icons";

interface SimulationEngineProps {
  loading: boolean;
  onRun: (request: AnalysisRunRequest) => void;
}

function ScenarioOption({
  label,
  selected,
  onSelect,
}: {
  label: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
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

export function SimulationEngine({ loading, onRun }: SimulationEngineProps) {
  const [scenario, setScenario] = useState<string | null>(null);

  const handleRun = () => {
    onRun({
      seed: DEFAULT_SEED,
      days: DEFAULT_ANALYSIS_DAYS,
      scenario,
      reference_seed: REFERENCE_SEED,
    });
  };

  return (
    <section className="panel relative overflow-hidden p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="label-mono">Demo control</p>
          <h2 className="mt-1 text-sm font-semibold">
            Incident Simulation Engine
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Detect → Correlate → Assess → Recommend → Respond
          </p>
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md px-4 py-2.5 text-sm font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 bg-primary text-primary-foreground hover:brightness-110"
        >
          {loading ? (
            <span
              aria-hidden="true"
              className="size-4 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground"
            />
          ) : (
            <PlayIcon className="size-4" />
          )}
          {loading ? "Analyzing…" : "Simulate Water Incident"}
        </button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label="Simulation scenario">
        <span className="text-xs text-muted-foreground">Scenario:</span>
        <ScenarioOption
          label="Normal operation"
          selected={scenario === null}
          onSelect={() => setScenario(null)}
        />
        <ScenarioOption
          label={DEMO_SCENARIO_ID}
          selected={scenario === DEMO_SCENARIO_ID}
          onSelect={() => setScenario(DEMO_SCENARIO_ID)}
        />
      </div>
    </section>
  );
}