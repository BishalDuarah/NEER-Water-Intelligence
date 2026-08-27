import { useEffect } from "react";
import { useState } from "react";
import { API_BASE_URL } from "../api/client";

type BackendStatus =
  | { state: "checking" }
  | { state: "connected" }
  | { state: "unreachable"; error: string };

export function BackendStatusPill() {
  const [status, setStatus] = useState<BackendStatus>({ state: "checking" });

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);

    fetch(`${API_BASE_URL}/health`, { signal: controller.signal })
      .then((res) => {
        if (res.ok) {
          setStatus({ state: "connected" });
        } else {
          setStatus({ state: "unreachable", error: `HTTP ${res.status}` });
        }
      })
      .catch((error: unknown) => {
        const message =
          error instanceof Error && error.name === "AbortError"
            ? "timed out"
            : "offline";
        setStatus({ state: "unreachable", error: message });
      })
      .finally(() => clearTimeout(timer));

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, []);

  if (status.state === "checking") {
    return (
      <span className="chip border-border/50 text-muted-foreground" role="status">
        Checking backend…
      </span>
    );
  }
  if (status.state === "connected") {
    return (
      <span
        className="chip bg-ok/15 text-ok border-ok/40"
        role="status"
        title="Backend reachable"
      >
        <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
        Backend connected
      </span>
    );
  }
  return (
    <span
      className="chip bg-warn/15 text-warn border-warn/40"
      role="status"
      title={`Backend unreachable: ${status.error}`}
    >
      <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
      Backend unreachable
    </span>
  );
}