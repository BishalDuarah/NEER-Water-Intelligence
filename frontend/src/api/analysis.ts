import type {
  AnalysisRunRequest,
  AnalysisRunResponse,
} from "../types/analysis";
import { API_BASE_URL } from "./client";

export class AnalysisApiError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "AnalysisApiError";
    this.status = status;
  }
}

function isAnalysisRunResponse(value: unknown): value is AnalysisRunResponse {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.run === "object" &&
    record.run !== null &&
    Array.isArray(record.incidents) &&
    typeof record.summary === "object" &&
    record.summary !== null
  );
}

export async function runAnalysis(
  request: AnalysisRunRequest,
): Promise<AnalysisRunResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/analysis/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw new AnalysisApiError(
      "Could not reach the NEER backend. Start it and try again.",
    );
  }

  if (response.status === 422) {
    throw new AnalysisApiError(
      "The analysis request was rejected as invalid.",
      response.status,
    );
  }
  if (!response.ok) {
    throw new AnalysisApiError(
      "The analysis service failed to produce a result.",
      response.status,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new AnalysisApiError(
      "The backend returned an unreadable response.",
      response.status,
    );
  }

  if (!isAnalysisRunResponse(payload)) {
    throw new AnalysisApiError(
      "The backend returned an unexpected response shape.",
    );
  }
  return payload;
}