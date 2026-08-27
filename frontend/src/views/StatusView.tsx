import { useEffect, useState } from "react";
import { fetchHealth } from "../api/client";
import type { HealthStatus } from "../types/health";

export function StatusView() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchHealth()
      .then((data) => {
        if (active) setHealth(data);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">Backend status</h2>
      {error ? (
        <p className="mt-2 text-sm text-red-600">
          Could not reach backend: {error}
        </p>
      ) : health ? (
        <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <dt className="text-slate-500">Status</dt>
          <dd className="text-slate-900">{health.status}</dd>
          <dt className="text-slate-500">Version</dt>
          <dd className="text-slate-900">{health.version}</dd>
          <dt className="text-slate-500">Environment</dt>
          <dd className="text-slate-900">{health.environment}</dd>
          <dt className="text-slate-500">Database</dt>
          <dd className="text-slate-900">{health.database}</dd>
          <dt className="text-slate-500">Timestamp</dt>
          <dd className="text-slate-900">{health.timestamp}</dd>
        </dl>
      ) : (
        <p className="mt-2 text-sm text-slate-500">Checking backend…</p>
      )}
    </section>
  );
}
