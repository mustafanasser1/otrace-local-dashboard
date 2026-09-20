import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileCheck,
  Lock,
  Network,
  RefreshCw,
  Scale,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

import { PageHeader, Panel } from "@/components/research/primitives";
import { fetchTraceLog, traceLogQueryKey, type TraceRecord } from "@/lib/trace-log";

export const Route = createFileRoute("/gdpr")({
  head: () => ({
    meta: [
      { title: "GDPR Evidence in Federated Learning — OTrace-FL" },
      {
        name: "description",
        content:
          "How the prototype adds GDPR context to federated learning events and records it in OTrace attestations as auditable evidence supporting later GDPR evaluation.",
      },
      { property: "og:title", content: "GDPR Evidence in Federated Learning — OTrace-FL" },
      {
        property: "og:description",
        content:
          "Federated learning events enriched with GDPR context and recorded as OTrace attestations: auditable evidence for GDPR evaluation and validation.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: GdprPage,
});

const FLOW = [
  {
    step: "Federated Learning Event",
    icon: <Network className="size-4" />,
    tone: "fl" as const,
    items: ["Local Training", "Update Submission", "Aggregation", "Deployment"],
  },
  {
    step: "GDPR Context",
    icon: <Scale className="size-4" />,
    tone: "fl" as const,
    items: ["Purpose", "Legal Basis", "Consent Reference", "GDPR Role", "Retention"],
  },
  {
    step: "OTrace Attestation",
    icon: <ShieldCheck className="size-4" />,
    tone: "otrace" as const,
    items: ["Actor", "Round", "Event", "Timestamp", "Trace ID"],
  },
  {
    step: "GDPR Evidence",
    icon: <FileCheck className="size-4" />,
    tone: "verified" as const,
    items: ["Accountability", "Traceability", "Consent Evidence", "Support for Evaluation"],
  },
];

const AREAS = [
  {
    title: "Accountability & Traceability",
    icon: <ShieldCheck className="size-4" />,
    tone: "text-otrace",
    body: "Who did what, when, and during which federated learning round.",
  },
  {
    title: "Lawful Processing & Consent",
    icon: <UserCheck className="size-4" />,
    tone: "text-fl",
    body: "Purpose, legal basis and a consent reference can accompany the recorded event.",
  },
  {
    title: "Data Protection",
    icon: <Lock className="size-4" />,
    tone: "text-fl",
    body: "Raw hospital data remains local; secure aggregation protects individual client updates.",
  },
  {
    title: "GDPR Evidence",
    icon: <FileCheck className="size-4" />,
    tone: "text-verified",
    body: "The resulting trace provides evidence that can support later evaluation and validation.",
  },
];

const ARTICLES = [
  {
    article: "Art. 5",
    title: "Principles of processing",
    note: "Each recorded event carries purpose and retention context, so processing can be reviewed afterwards.",
  },
  {
    article: "Art. 6",
    title: "Lawfulness of processing",
    note: "Attestations record the legal basis stated for the federated learning event.",
  },
  {
    article: "Art. 7",
    title: "Conditions for consent",
    note: "Where consent is the basis, the event references the consent record held by the OTrace service.",
  },
  {
    article: "Art. 25",
    title: "Data protection by design",
    note: "Raw hospital data stays local and only aggregated model updates leave each client group.",
  },
  {
    article: "Art. 30",
    title: "Records of processing",
    note: "The trace store keeps a queryable record of every federated learning event in the run.",
  },
  {
    article: "Art. 32",
    title: "Security of processing",
    note: "Secure aggregation is applied to client updates in the experimental pipeline.",
  },
] as const;

function formatTime(iso: string | undefined): string {
  if (!iso) return "—";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return iso;
  return new Date(ms).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Pick the attestation carrying the most GDPR context, so the example is real and rich. */
function pickExample(records: TraceRecord[]): TraceRecord | undefined {
  let best: TraceRecord | undefined;
  let bestScore = -1;
  for (const r of records) {
    const score = [r.purpose, r.legalBasis, r.consentReference, r.gdprRole, r.retentionPeriod, r.round, r.actor]
      .filter((v) => v !== undefined && v !== "")
      .length;
    if (score > bestScore) {
      bestScore = score;
      best = r;
    }
  }
  return best;
}

function GdprPage() {
  const traceQuery = useQuery({
    queryKey: traceLogQueryKey,
    queryFn: ({ signal }) => fetchTraceLog(signal),
    retry: false,
    staleTime: 30_000,
  });

  const traceRecords = useMemo(() => traceQuery.data?.records ?? [], [traceQuery.data]);
  const example = useMemo(() => pickExample(traceRecords), [traceRecords]);

  const [showRaw, setShowRaw] = useState(false);
  const refreshing = traceQuery.isFetching;

  return (
    <div>
      <PageHeader
        title="GDPR Evidence in Federated Learning"
        subtitle="Adding GDPR context to Federated Learning events and recording it in OTrace as auditable evidence."
        right={
          <button
            type="button"
            onClick={() => void traceQuery.refetch()}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3.5 py-2 text-[13.5px] font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-60"
          >
            <RefreshCw className={`size-4 ${refreshing ? "animate-spin" : ""}`} />
            {refreshing ? "Refreshing…" : "Refresh"}
          </button>
        }
      />

      <Panel
        title="How GDPR Evidence Is Produced"
        accent="fl"
        icon={<Scale className="size-4" />}
        className="mb-6"
        description="Each federated learning event is enriched with GDPR context and recorded as an OTrace attestation."
      >
        <ol className="grid gap-3 lg:grid-cols-4">
          {FLOW.map((s, i) => (
            <li key={s.step} className="relative rounded-md border border-border bg-secondary/30 px-4 py-4">
              <div className="flex items-center gap-2">
                <span
                  className={
                    s.tone === "fl"
                      ? "text-fl"
                      : s.tone === "otrace"
                        ? "text-otrace"
                        : "text-verified"
                  }
                >
                  {s.icon}
                </span>
                <span className="text-[14px] font-semibold text-foreground">{s.step}</span>
              </div>
              <ul className="mt-3 space-y-1.5">
                {s.items.map((it) => (
                  <li key={it} className="text-[13px] leading-snug text-muted-foreground">
                    {it}
                  </li>
                ))}
              </ul>
              {i < FLOW.length - 1 ? (
                <ChevronRight className="absolute -right-3 top-1/2 hidden size-4 -translate-y-1/2 text-border lg:block" />
              ) : null}
            </li>
          ))}
        </ol>
      </Panel>

      <Panel
        title="What OTrace Records"
        accent="otrace"
        icon={<ShieldCheck className="size-4" />}
        className="mb-6"
        description="One real attestation from the live trace, shown as recorded — fields absent from the record are not displayed."
      >
        {traceQuery.error ? (
          <div className="flex items-start gap-3 rounded-md border border-otrace/25 bg-otrace-soft px-4 py-4 text-[13.5px] text-otrace">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <div>
              <div className="font-medium">Trace unavailable</div>
              <p className="mt-1 text-muted-foreground">{(traceQuery.error as Error).message}.</p>
            </div>
          </div>
        ) : traceQuery.isLoading ? (
          <div className="py-8 text-center text-[13.5px] text-muted-foreground">Reading the trace…</div>
        ) : !example ? (
          <div className="py-8 text-center text-[13.5px] text-muted-foreground">
            The trace store returned no attestations.
          </div>
        ) : (
          <>
            <div className="grid gap-4 lg:grid-cols-2">
              <FieldGroup
                title="FL Information"
                accent="fl"
                fields={[
                  ["Event Type", example.eventType],
                  ["Client / Actor", example.actor],
                  ["Round", example.round !== undefined ? String(example.round) : undefined],
                  ["Timestamp", example.eventTimestamp ?? example.timestamp ? formatTime(example.eventTimestamp ?? example.timestamp) : undefined],
                  ["Model Version", example.modelVersion],
                ]}
              />
              <FieldGroup
                title="GDPR Context"
                accent="otrace"
                fields={[
                  ["Purpose", example.purpose],
                  ["Legal Basis", example.legalBasis],
                  ["Consent Reference", example.consentReference],
                  ["GDPR Role", example.gdprRole],
                  ["Retention", example.retentionPeriod],
                ]}
              />
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-secondary/40 px-4 py-3">
              <p className="text-[13px] text-muted-foreground">
                Recorded as OTrace attestation{" "}
                <span className="font-mono text-foreground">{example.traceId}</span>
              </p>
              <button
                type="button"
                onClick={() => setShowRaw((v) => !v)}
                className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-[13px] font-medium text-foreground transition-colors hover:bg-secondary"
              >
                <ChevronDown className={`size-4 transition-transform ${showRaw ? "rotate-180" : ""}`} />
                {showRaw ? "Hide actual attestation" : "View actual attestation"}
              </button>
            </div>
            {showRaw ? (
              <pre className="mt-3 max-h-96 overflow-auto rounded-md border border-border bg-secondary/50 p-4 text-[12px] leading-relaxed text-foreground">
                {JSON.stringify(example.raw, null, 2)}
              </pre>
            ) : null}
          </>
        )}
      </Panel>

      <Panel
        title="GDPR Areas Supported"
        accent="verified"
        icon={<FileCheck className="size-4" />}
        className="mb-6"
        description="What this prototype demonstrates. No claim of full GDPR compliance or certification is made."
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {AREAS.map((a) => (
            <div key={a.title} className="rounded-md border border-border bg-secondary/30 px-4 py-3">
              <div className="flex items-center gap-2 text-[13.5px] font-semibold text-foreground">
                <span className={a.tone}>{a.icon}</span>
                {a.title}
              </div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">{a.body}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel
        title="GDPR Articles Relevant to the Prototype"
        accent="fl"
        icon={<ShieldCheck className="size-4" />}
        description="How each article relates to what the prototype actually implements. No assessment of legal compliance is made."
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {ARTICLES.map((a) => (
            <div key={a.article} className="rounded-md border border-border bg-secondary/30 px-4 py-3">
              <div className="text-[13.5px] font-semibold text-foreground">{a.article}</div>
              <div className="mt-1 text-[13px] text-foreground">{a.title}</div>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">{a.note}</p>
            </div>
          ))}
        </div>
      </Panel>

    </div>
  );
}

function FieldGroup({
  title,
  accent,
  fields,
}: {
  title: string;
  accent: "fl" | "otrace";
  fields: Array<[string, string | undefined]>;
}) {
  const present = fields.filter(([, v]) => v !== undefined && v !== "");
  return (
    <div className="rounded-md border border-border">
      <div
        className={`border-b border-border px-4 py-2.5 text-[13px] font-semibold ${
          accent === "fl" ? "text-fl" : "text-otrace"
        }`}
      >
        {title}
      </div>
      {present.length === 0 ? (
        <p className="px-4 py-3 text-[13px] text-muted-foreground">
          No fields of this kind are present in the record.
        </p>
      ) : (
        present.map(([label, value]) => (
          <div key={label} className="flex gap-4 border-b border-border/70 px-4 py-2.5 last:border-b-0">
            <span className="w-44 shrink-0 text-[13px] text-muted-foreground">{label}</span>
            <span className="break-all text-[13.5px] text-foreground">{value}</span>
          </div>
        ))
      )}
    </div>
  );
}