/**
 * Typed client for the REAL consent records held by the OTrace service.
 *
 * Verified against the live OpenAPI document. The consents router exposes only:
 *
 *   GET /consents/{consent_id}/        → Consent
 *   GET /consents/list/{user_name}/    → Consent[]
 *
 * There is NO "list all consents" operation. Consent references are therefore
 * discovered from the attestations returned by `GET /trace/search/`
 * (`action.information.consent_reference`), each reference is resolved with
 * `GET /consents/{id}/`, and every consent of the resolved subjects is then
 * loaded with `GET /consents/list/{user_name}/`. Nothing is ever synthesised:
 * when the service does not answer, the page shows an honest error state.
 *
 * Consent schema (verified):
 *   { id, operator: { name }, user: { name },
 *     data: { description }, operations_permitted: [{ operation_type }],
 *     expiry_timestamp, state: "offered" | "accepted" | "denied" | "revoked" }
 */

import { API_BASE } from "./api";
import { fetchTraceLog } from "./trace-log";

export const CONSENT_BY_ID_PATH = "/consents/{consent_id}/";
export const CONSENT_LIST_PATH = "/consents/list/{user_name}/";
export const CONSENT_ENDPOINTS = [CONSENT_BY_ID_PATH, CONSENT_LIST_PATH] as const;

export const CONSENT_TIMEOUT_MS = 30_000;

export interface RawConsent {
  [key: string]: unknown;
}

/** Normalised consent row, mapped 1:1 from the verified backend schema. */
export interface ConsentRecord {
  consentId: string;
  /** `user.name` — pseudonymous subject identifier. */
  subject: string | undefined;
  /** `operator.name` — the party operating on the data. */
  operator: string | undefined;
  /** `data.description` — the data categories covered by the consent. */
  dataDescription: string | undefined;
  /** `operations_permitted[].operation_type`, joined. */
  operations: string | undefined;
  /** `state` — offered | accepted | denied | revoked. */
  status: string | undefined;
  /** `expiry_timestamp`. */
  expiresAt: string | undefined;
  raw: RawConsent;
}

function str(v: unknown): string | undefined {
  if (typeof v === "string" && v.trim() !== "") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return undefined;
}

function obj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
}

export function normaliseConsent(raw: RawConsent, index: number): ConsentRecord {
  const ops = Array.isArray(raw["operations_permitted"])
    ? (raw["operations_permitted"] as unknown[])
        .map((o) => str(obj(o)["operation_type"]))
        .filter(Boolean)
        .join(", ")
    : undefined;
  return {
    consentId: str(raw["id"]) ?? `consent-${index}`,
    subject: str(obj(raw["user"])["name"]),
    operator: str(obj(raw["operator"])["name"]),
    dataDescription: str(obj(raw["data"])["description"]),
    operations: ops && ops !== "" ? ops : undefined,
    status: str(raw["state"]),
    expiresAt: str(raw["expiry_timestamp"]),
    raw,
  };
}

export function consentTime(c: ConsentRecord): number {
  if (!c.expiresAt) return 0;
  const ms = Date.parse(c.expiresAt);
  return Number.isNaN(ms) ? 0 : ms;
}

export class ConsentLogError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConsentLogError";
  }
}

export interface ConsentLogResult {
  records: ConsentRecord[];
  /** Human-readable description of the real operations used. */
  endpoint: string;
  /** Consent references discovered in the attestation trace. */
  discoveredRefs: number;
  fetchedAt: number;
}

async function getJson(url: string, signal: AbortSignal): Promise<unknown | null> {
  try {
    const res = await fetch(url, { headers: { Accept: "application/json" }, signal });
    if (!res.ok) return null;
    return (await res.json()) as unknown;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    return null;
  }
}

/**
 * Fetch the real consent records. Throws `ConsentLogError` on any failure so
 * the page can render an honest error state — it never returns substitute rows.
 */
export async function fetchConsents(signal?: AbortSignal): Promise<ConsentLogResult> {
  if (typeof window === "undefined") {
    throw new ConsentLogError("Consent records are not requested during server render");
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), CONSENT_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort);

  try {
    // 1. Discover consent references from the real attestation trace.
    const refs = new Set<string>();
    try {
      const trace = await fetchTraceLog(controller.signal);
      for (const r of trace.records) {
        if (r.consentReference) refs.add(r.consentReference);
      }
    } catch {
      throw new ConsentLogError("OTrace service unreachable (GET /trace/search/ did not answer)");
    }

    if (refs.size === 0) {
      return {
        records: [],
        endpoint: `GET ${CONSENT_BY_ID_PATH} · GET ${CONSENT_LIST_PATH}`,
        discoveredRefs: 0,
        fetchedAt: Date.now(),
      };
    }

    // 2. Resolve each reference against the real consent store.
    const byId = new Map<string, RawConsent>();
    const resolved = await Promise.all(
      [...refs].map((id) => getJson(`${API_BASE}/consents/${encodeURIComponent(id)}/`, controller.signal)),
    );
    for (const r of resolved) {
      const rec = obj(r);
      const id = str(rec["id"]);
      if (id) byId.set(id, rec);
    }

    if (byId.size === 0) {
      throw new ConsentLogError(
        `Consent store returned no record for ${refs.size} referenced consent id(s) (GET ${CONSENT_BY_ID_PATH})`,
      );
    }

    // 3. Expand to every consent held for the resolved subjects.
    const users = new Set<string>();
    for (const rec of byId.values()) {
      const name = str(obj(rec["user"])["name"]);
      if (name) users.add(name);
    }
    const lists = await Promise.all(
      [...users].map((u) => getJson(`${API_BASE}/consents/list/${encodeURIComponent(u)}/`, controller.signal)),
    );
    for (const list of lists) {
      if (!Array.isArray(list)) continue;
      for (const item of list) {
        const rec = obj(item);
        const id = str(rec["id"]);
        if (id) byId.set(id, rec);
      }
    }

    const records = [...byId.values()].map((r, i) => normaliseConsent(r, i));
    records.sort((a, b) => (a.subject ?? "").localeCompare(b.subject ?? "") || a.consentId.localeCompare(b.consentId));

    return {
      records,
      endpoint: `GET ${CONSENT_BY_ID_PATH} · GET ${CONSENT_LIST_PATH}`,
      discoveredRefs: refs.size,
      fetchedAt: Date.now(),
    };
  } catch (err) {
    if (err instanceof ConsentLogError) throw err;
    const aborted = err instanceof DOMException && err.name === "AbortError";
    throw new ConsentLogError(
      aborted
        ? `No response within ${CONSENT_TIMEOUT_MS / 1000}s (OTrace unreachable)`
        : "OTrace consent service unreachable",
    );
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export const consentQueryKey = ["otrace", "consents"] as const;