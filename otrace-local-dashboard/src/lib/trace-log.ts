/**
 * Typed client for the REAL OTrace attestation store.
 *
 *   GET {API_BASE}/trace/search/            → Attestation[]
 *
 * This is the OTrace service's own search endpoint (tag "Trace", operation
 * `search_attestations_trace_search__get`). Records are produced by the FL
 * pipeline during traced runs. Nothing here is synthesised: when the endpoint
 * is unreachable the UI shows an honest error/empty state instead of rows.
 */

import { API_BASE } from "./api";

export const TRACE_SEARCH_ENDPOINT = `${API_BASE}/trace/search/`;

/** Attestations can be a large array; keep the request bounded but generous. */
export const TRACE_TIMEOUT_MS = 30_000;

/** Raw attestation as returned by the OTrace service. */
export interface RawAttestation {
  id?: unknown;
  timestamp?: unknown;
  party?: { name?: unknown; data_controller?: unknown } | null;
  action?: { type?: unknown; information?: Record<string, unknown> | null } | null;
  [key: string]: unknown;
}

/** Normalised view used by the transaction log table. Every field is optional
 *  because the backend record — not the frontend — decides what exists. */
export interface TraceRecord {
  /** Attestation / trace identifier as recorded. */
  traceId: string;
  /** Top-level attestation timestamp (ISO string as returned). */
  timestamp: string | undefined;
  /** Event timestamp inside the action information, when present. */
  eventTimestamp: string | undefined;
  eventType: string | undefined;
  actionType: string | undefined;
  actor: string | undefined;
  dataController: string | undefined;
  round: number | undefined;
  group: number | undefined;
  purpose: string | undefined;
  legalBasis: string | undefined;
  retentionPeriod: string | undefined;
  gdprRole: string | undefined;
  gdprArticle: string | undefined;
  consentReference: string | undefined;
  modelVersion: string | undefined;
  operation: string | undefined;
  /** The untouched record, shown verbatim in the details drawer. */
  raw: RawAttestation;
}

function str(v: unknown): string | undefined {
  if (typeof v === "string" && v.trim() !== "") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return undefined;
}

function num(v: unknown): number | undefined {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return undefined;
}

function pick(info: Record<string, unknown>, keys: string[]): unknown {
  for (const k of keys) {
    if (info[k] !== undefined && info[k] !== null && info[k] !== "") return info[k];
  }
  return undefined;
}

export function normaliseAttestation(raw: RawAttestation, index: number): TraceRecord {
  const info = (raw.action?.information ?? {}) as Record<string, unknown>;
  return {
    traceId: str(raw.id) ?? str(pick(info, ["trace_id", "attestation_id"])) ?? `record-${index}`,
    timestamp: str(raw.timestamp),
    eventTimestamp: str(info["timestamp"]),
    eventType: str(pick(info, ["event_type", "eventType"])) ?? str(raw.action?.type),
    actionType: str(raw.action?.type),
    actor: str(raw.party?.name) ?? str(pick(info, ["client", "party", "actor"])),
    dataController:
      str(raw.party?.data_controller) ?? str(pick(info, ["otrace_data_controller", "data_controller"])),
    round: num(pick(info, ["training_round", "round", "fl_round"])),
    group: num(pick(info, ["hospital_group", "group", "client_id"])),
    purpose: str(info["purpose"]),
    legalBasis: str(pick(info, ["legal_basis", "legalBasis"])),
    retentionPeriod: str(pick(info, ["retention_period", "retention"])),
    gdprRole: str(pick(info, ["data_controller_role", "gdpr_role", "role"])),
    gdprArticle: str(pick(info, ["gdpr_article", "article"])),
    consentReference: str(pick(info, ["consent_reference", "consent_id", "consent"])),
    modelVersion: str(pick(info, ["model_version", "global_model_version", "version"])),
    operation: str(info["operation"]),
    raw,
  };
}

/** Sortable epoch value; falls back to 0 when no parsable timestamp exists. */
export function recordTime(r: TraceRecord): number {
  const t = r.eventTimestamp ?? r.timestamp;
  if (!t) return 0;
  const ms = Date.parse(t);
  return Number.isNaN(ms) ? 0 : ms;
}

export interface TraceLogResult {
  records: TraceRecord[];
  fetchedAt: number;
}

export class TraceLogError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TraceLogError";
  }
}

/**
 * Fetch the real attestation log. Throws `TraceLogError` on any failure so the
 * page can render an honest error state — it never returns substitute rows.
 */
export async function fetchTraceLog(signal?: AbortSignal): Promise<TraceLogResult> {
  if (typeof window === "undefined") {
    throw new TraceLogError("Trace log is not requested during server render");
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TRACE_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    const res = await fetch(TRACE_SEARCH_ENDPOINT, {
      headers: { Accept: "application/json" },
      // Never reuse an HTTP-cached response from a previously unreachable host.
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      throw new TraceLogError(`OTrace responded ${res.status} ${res.statusText}`.trim());
    }
    const json = (await res.json()) as unknown;
    const list: unknown = Array.isArray(json)
      ? json
      : ((json as { attestations?: unknown; results?: unknown; items?: unknown })?.attestations ??
        (json as { results?: unknown })?.results ??
        (json as { items?: unknown })?.items);
    if (!Array.isArray(list)) {
      throw new TraceLogError("Unexpected response shape from /trace/search/");
    }
    return {
      records: list.map((r, i) => normaliseAttestation((r ?? {}) as RawAttestation, i)),
      fetchedAt: Date.now(),
    };
  } catch (err) {
    if (err instanceof TraceLogError) throw err;
    const aborted = err instanceof DOMException && err.name === "AbortError";
    throw new TraceLogError(
      aborted ? `No response within ${TRACE_TIMEOUT_MS / 1000}s (OTrace unreachable)` : "OTrace service unreachable",
    );
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export const traceLogQueryKey = ["otrace", "trace-log"] as const;