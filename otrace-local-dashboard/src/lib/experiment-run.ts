/**
 * Typed frontend contract for the REAL FastAPI experiment-run endpoint.
 *
 *   POST {VITE_OTRACE_API_BASE}/ui/api/experiment/run
 *
 * The Python side must delegate to the existing
 * `run_experiment(consent_sample: int = 60, seed: int = 42) -> dict`
 * in `fl-pipeline/run_traced_experiment.py`. This module NEVER simulates a run
 * and never substitutes fallback values as a run result.
 *
 * See `docs/FASTAPI_RUN_ENDPOINT.md` for the full server-side contract.
 */

import type { ExperimentSummary } from "./research-data";

import { API_BASE } from "./api";

export const RUN_ENDPOINT = `${API_BASE}/ui/api/experiment/run`;

/** A real traced run can take minutes; keep the client patient but bounded. */
export const RUN_TIMEOUT_MS = 600_000;

export interface RunExperimentRequest {
  consent_sample?: number;
  seed?: number;
}

/** Successful payload: the backend returns the freshly recorded run summary. */
export interface RunExperimentResponse {
  status: "completed";
  started_at?: string;
  finished_at?: string;
  duration_sec?: number;
  /** Same shape as `GET /ui/api/summary`; produced by this run only. */
  summary?: Partial<ExperimentSummary>;
}

export type RunState =
  | { phase: "idle" }
  | { phase: "starting" }
  | { phase: "running"; startedAt: number }
  | { phase: "completed"; finishedAt: number; result: RunExperimentResponse }
  | { phase: "failed"; error: string; unavailable: boolean };

export class RunEndpointUnavailableError extends Error {
  readonly unavailable = true;
  constructor(message: string) {
    super(message);
    this.name = "RunEndpointUnavailableError";
  }
}

export class RunFailedError extends Error {
  readonly unavailable = false;
  constructor(message: string) {
    super(message);
    this.name = "RunFailedError";
  }
}

/** Reads FastAPI's `detail` field (string or validation array) as readable text. */
async function readDetail(res: Response): Promise<string> {
  const raw = await res.text().catch(() => "");
  if (!raw) return "";
  try {
    const parsed = JSON.parse(raw) as { detail?: unknown };
    const d = parsed?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((item) => {
          const e = item as { loc?: unknown[]; msg?: string };
          const field = Array.isArray(e.loc) ? e.loc.filter((p) => p !== "body").join(".") : "";
          return field ? `${field}: ${e.msg ?? "invalid value"}` : (e.msg ?? "invalid value");
        })
        .join("; ");
    }
  } catch {
    /* not JSON — fall through to the raw text */
  }
  return raw.slice(0, 300);
}

/** Turns backend status codes into wording a reader of the thesis can act on. */
export function explainStatus(status: number, statusText: string, detail: string): string {
  const suffix = detail ? ` Backend said: ${detail}` : "";
  switch (status) {
    case 409:
      return `A run is already in progress on the backend. Wait for it to finish before starting another one.${suffix}`;
    case 503:
      return `The OTrace service is unavailable, so the run cannot be traced and was not started. Start the OTrace service and try again.${suffix}`;
    case 422:
      return `The backend rejected the parameters as invalid. Check consent_sample and seed (both must be whole numbers).${suffix}`;
    case 500:
      return `The run failed on the backend while executing run_experiment().${suffix}`;
    default:
      return `Run failed: ${status} ${statusText}.${suffix}`.trim();
  }
}

/**
 * Executes a real run on the backend. Throws:
 *  - `RunEndpointUnavailableError` when the endpoint is missing (404/405) or
 *    the backend is unreachable — the UI then shows "Run endpoint unavailable"
 *    and keeps the verified fallback display separate.
 *  - `RunFailedError` when the backend accepted the request but the run failed.
 */
export async function runExperiment(
  body: RunExperimentRequest = {},
  signal?: AbortSignal,
): Promise<RunExperimentResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), RUN_TIMEOUT_MS);
  const onOuterAbort = () => controller.abort();
  signal?.addEventListener("abort", onOuterAbort);

  try {
    let res: Response;
    try {
      res = await fetch(RUN_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch {
      throw new RunEndpointUnavailableError("Run endpoint unavailable — backend unreachable");
    }

    if (res.status === 404 || res.status === 405) {
      throw new RunEndpointUnavailableError(
        `Run endpoint unavailable — backend responded ${res.status}`,
      );
    }
    if (!res.ok) {
      const detail = await readDetail(res);
      throw new RunFailedError(explainStatus(res.status, res.statusText, detail));
    }

    let json: unknown;
    try {
      json = await res.json();
    } catch {
      throw new RunFailedError("Run failed: backend returned a non-JSON response");
    }

    const payload = json as Partial<RunExperimentResponse> & { detail?: string };
    if (payload?.status !== "completed") {
      throw new RunFailedError(payload?.detail ?? "Run failed: backend did not report completion");
    }
    return payload as RunExperimentResponse;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onOuterAbort);
  }
}