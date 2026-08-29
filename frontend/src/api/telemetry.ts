import type { TelemetryRunRequest, TelemetryRunResponse } from "../types/telemetry";
import { API_BASE_URL } from "./client";

export class TelemetryApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "TelemetryApiError";
    this.status = status;
  }
}

function isTelemetryRunResponse(
  value: unknown,
): value is TelemetryRunResponse {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.run === "object" &&
    record.run !== null &&
    Array.isArray(record.zones) &&
    Array.isArray(record.measurements) &&
    Array.isArray(record.scenarios)
  );
}

export async function runTelemetry(
  request: TelemetryRunRequest,
): Promise<TelemetryRunResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/telemetry/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw new TelemetryApiError(
      "Could not reach the NEER backend. Start it and try again.",
    );
  }

  if (response.status === 422) {
    throw new TelemetryApiError(
      "The telemetry request was rejected as invalid.",
      response.status,
    );
  }
  if (!response.ok) {
    throw new TelemetryApiError(
      "The telemetry service failed to produce a result.",
      response.status,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new TelemetryApiError(
      "The backend returned an unreadable response.",
      response.status,
    );
  }

  if (!isTelemetryRunResponse(payload)) {
    throw new TelemetryApiError(
      "The backend returned an unexpected response shape.",
    );
  }
  return payload;
}
