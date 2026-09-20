import { FALLBACK_SUMMARY, type ExperimentSummary } from "./research-data";

/**
 * Typed client for the existing Python/FastAPI backend.
 *
 * The backend exposes `GET /ui/api/summary`. When it is not reachable from this
 * prototype UI we fall back to the verified recorded values so the interface
 * stays inspectable offline. The source of the data is always reported.
 *
 * ── Pointing this frontend at a local FastAPI host ───────────────────────────
 * The API base URL is configurable through a SINGLE environment variable:
 *
 *   VITE_OTRACE_API_BASE
 *
 * Default is an empty string, i.e. same-origin requests — the correct setting
 * when this UI is served by FastAPI itself (`/ui/api/summary`).
 *
 * For local development against a FastAPI process on another port, create a
 * `.env` file at the project root with, for example:
 *
 *   VITE_OTRACE_API_BASE=http://127.0.0.1:8000
 *
 * The FastAPI service must then allow CORS for the frontend origin. No other
 * backend, cloud service or database is involved.
 */

export type SummarySource = "backend" | "fallback";

export interface SummaryResult {
  data: ExperimentSummary;
  source: SummarySource;
  error?: string;
}

/**
 * Default backend base used when no `VITE_OTRACE_API_BASE` is injected:
 * the user's local FastAPI/OTrace service.
 */
export const DEFAULT_API_BASE = "http://127.0.0.1:8080";

const ENV_API_BASE = (import.meta.env["VITE_OTRACE_API_BASE"] as string | undefined)?.trim();

export const API_BASE = ENV_API_BASE && ENV_API_BASE !== "" ? ENV_API_BASE : DEFAULT_API_BASE;

/** Request timeout in milliseconds; a slow/absent backend must not hang the UI. */
export const SUMMARY_TIMEOUT_MS = 6000;

export const SUMMARY_ENDPOINT = `${API_BASE}/ui/api/summary`;

function mergeSummary(partial: unknown): ExperimentSummary {
  if (!partial || typeof partial !== "object") return FALLBACK_SUMMARY;
  const p = partial as Partial<ExperimentSummary>;
  return {
    ...FALLBACK_SUMMARY,
    ...p,
    meta: { ...FALLBACK_SUMMARY.meta, ...(p.meta ?? {}) },
    dataset: { ...FALLBACK_SUMMARY.dataset, ...(p.dataset ?? {}) },
    federated: { ...FALLBACK_SUMMARY.federated, ...(p.federated ?? {}) },
    privacy: { ...FALLBACK_SUMMARY.privacy, ...(p.privacy ?? {}) },
    metrics: { ...FALLBACK_SUMMARY.metrics, ...(p.metrics ?? {}) },
    trace: { ...FALLBACK_SUMMARY.trace, ...(p.trace ?? {}) },
    erasure: { ...FALLBACK_SUMMARY.erasure, ...(p.erasure ?? {}) },
    runtime: { ...FALLBACK_SUMMARY.runtime, ...(p.runtime ?? {}) },
    metamorphicRelations:
      p.metamorphicRelations ?? FALLBACK_SUMMARY.metamorphicRelations,
    gdprArticles: p.gdprArticles ?? FALLBACK_SUMMARY.gdprArticles,
    ...(p.capabilities ? { capabilities: p.capabilities } : {}),
  };
}

/**
 * Deterministic: never throws, never logs. On any failure (network error,
 * non-2xx, timeout, invalid JSON) it returns the verified fallback summary
 * together with a short, human-readable reason.
 */
export async function fetchSummary(signal?: AbortSignal): Promise<SummaryResult> {
  if (typeof window === "undefined") {
    return { data: FALLBACK_SUMMARY, source: "fallback", error: "Not requested during server render" };
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), SUMMARY_TIMEOUT_MS);
  const onOuterAbort = () => controller.abort();
  signal?.addEventListener("abort", onOuterAbort);

  try {
    const res = await fetch(SUMMARY_ENDPOINT, {
      headers: { Accept: "application/json" },
      // Never reuse an HTTP-cached response from a previously unreachable host.
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      return {
        data: FALLBACK_SUMMARY,
        source: "fallback",
        error: `Backend responded ${res.status} ${res.statusText}`.trim(),
      };
    }
    const json = (await res.json()) as unknown;
    return { data: mergeSummary(json), source: "backend" };
  } catch (err) {
    const aborted = err instanceof DOMException && err.name === "AbortError";
    return {
      data: FALLBACK_SUMMARY,
      source: "fallback",
      error: aborted
        ? `No response within ${SUMMARY_TIMEOUT_MS / 1000}s (backend unreachable)`
        : "Backend unreachable",
    };
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener("abort", onOuterAbort);
  }
}

export const summaryQueryOptions = {
  queryKey: ["otrace", "summary"] as const,
  queryFn: ({ signal }: { signal?: AbortSignal }) => fetchSummary(signal),
  staleTime: 60_000,
  retry: false,
};