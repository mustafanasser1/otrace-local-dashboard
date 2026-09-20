import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowDownUp,
  CheckCircle2,
  Database,
  FileCheck,
  ListTree,
  RefreshCw,
  Route as RouteIcon,
  Search,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { PageHeader, Panel, StatCard, Chip } from "@/components/research/primitives";
import { IconPipeline } from "@/components/research/visuals";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import {
  fetchTraceLog,
  recordTime,
  traceLogQueryKey,
  TRACE_SEARCH_ENDPOINT,
  type TraceRecord,
} from "@/lib/trace-log";

export const Route = createFileRoute("/otrace")({
  head: () => ({
    meta: [
      { title: "OTrace Transaction Log — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Live OTrace attestation log recorded during federated learning runs: event type, actor, round, GDPR context and full record details.",
      },
      { property: "og:title", content: "OTrace Transaction Log — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content:
          "The actual OTrace audit log generated during FL runs, read directly from the OTrace attestation store.",
      },
    ],
  }),
  component: OTracePage,
});

const EVENT_ORDER = [
  "LocalTrainingEvent",
  "UpdateSubmissionEvent",
  "AggregationEvent",
  "DeploymentEvent",
] as const;

function formatTime(iso: string | undefined): string {
  if (!iso) return "—";
  const ms = Date.parse(iso);
  if (Number.isNaN(ms)) return iso;
  return new Date(ms).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function OTracePage() {
  const { data, error, isFetching, refetch, isLoading } = useQuery({
    queryKey: traceLogQueryKey,
    queryFn: ({ signal }) => fetchTraceLog(signal),
    // A transient network hiccup must not pin the page to its offline state.
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    staleTime: 30_000,
  });


  const records = useMemo(() => data?.records ?? [], [data]);

  const [eventFilter, setEventFilter] = useState("all");
  const [roundFilter, setRoundFilter] = useState("all");
  const [actorFilter, setActorFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [newestFirst, setNewestFirst] = useState(true);
  const [selected, setSelected] = useState<TraceRecord | null>(null);

  const eventTypes = useMemo(() => {
    const set = new Set(records.map((r) => r.eventType).filter(Boolean) as string[]);
    return Array.from(set).sort(
      (a, b) =>
        (EVENT_ORDER.indexOf(a as (typeof EVENT_ORDER)[number]) + 1 || 99) -
        (EVENT_ORDER.indexOf(b as (typeof EVENT_ORDER)[number]) + 1 || 99),
    );
  }, [records]);

  const rounds = useMemo(() => {
    const set = new Set(records.map((r) => r.round).filter((r): r is number => r !== undefined));
    return Array.from(set).sort((a, b) => a - b);
  }, [records]);

  const actors = useMemo(() => {
    const set = new Set(records.map((r) => r.actor).filter(Boolean) as string[]);
    return Array.from(set).sort();
  }, [records]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const r of records) if (r.eventType) c[r.eventType] = (c[r.eventType] ?? 0) + 1;
    return c;
  }, [records]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = records.filter((r) => {
      if (eventFilter !== "all" && r.eventType !== eventFilter) return false;
      if (roundFilter !== "all" && String(r.round ?? "") !== roundFilter) return false;
      if (actorFilter !== "all" && r.actor !== actorFilter) return false;
      if (q && !r.traceId.toLowerCase().includes(q)) return false;
      return true;
    });
    list.sort((a, b) => (newestFirst ? recordTime(b) - recordTime(a) : recordTime(a) - recordTime(b)));
    return list;
  }, [records, eventFilter, roundFilter, actorFilter, search, newestFirst]);

  const VISIBLE = 250;
  const shown = filtered.slice(0, VISIBLE);

  return (
    <div>
      <PageHeader
        title="OTrace Transaction Log"
        subtitle="The actual OTrace audit log generated during federated learning runs, read live from the OTrace attestation store. Each row is a recorded attestation with its GDPR context; the log supports GDPR-aware traceability, accountability and compliance validation."
        right={
          <button
            type="button"
            onClick={() => void refetch()}
            className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3.5 py-2 text-[13.5px] font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-60"
            disabled={isFetching}
          >
            <RefreshCw className={`size-4 ${isFetching ? "animate-spin" : ""}`} />
            {isFetching ? "Refreshing…" : "Refresh"}
          </button>
        }
      />

      <div className="mb-7 grid grid-cols-2 gap-4 xl:grid-cols-5">
        <StatCard
          label="Total Records"
          value={String(records.length)}
          accent="otrace"
          icon={<ListTree className="size-4" />}
        />
        <StatCard
          label="LocalTrainingEvent"
          value={String(counts["LocalTrainingEvent"] ?? 0)}
          accent="fl"
          icon={<Activity className="size-4" />}
        />
        <StatCard
          label="UpdateSubmissionEvent"
          value={String(counts["UpdateSubmissionEvent"] ?? 0)}
          accent="fl"
          icon={<Upload className="size-4" />}
        />
        <StatCard
          label="AggregationEvent"
          value={String(counts["AggregationEvent"] ?? 0)}
          accent="otrace"
          icon={<Database className="size-4" />}
        />
        <StatCard
          label="DeploymentEvent"
          value={String(counts["DeploymentEvent"] ?? 0)}
          accent="verified"
          icon={<CheckCircle2 className="size-4" />}
        />
      </div>

      <Panel
        title="Recorded Lifecycle Stages"
        accent="otrace"
        icon={<RouteIcon className="size-4" />}
        className="mb-6"
        description="Stages the OTrace attestations cover. Records are independent attestations; the strip does not assert a linkage between individual transactions."
      >
        <IconPipeline
          accent="otrace"
          nodes={[
            { icon: <ShieldCheck className="size-4 text-otrace" />, label: "Hospital / Client", sub: "party recorded per attestation" },
            { icon: <Activity className="size-4 text-otrace" />, label: "Local Training", sub: `${counts["LocalTrainingEvent"] ?? 0} records` },
            { icon: <Upload className="size-4 text-otrace" />, label: "Update Submission", sub: `${counts["UpdateSubmissionEvent"] ?? 0} records` },
            { icon: <Database className="size-4 text-otrace" />, label: "Aggregation", sub: `${counts["AggregationEvent"] ?? 0} records` },
            { icon: <FileCheck className="size-4 text-otrace" />, label: "Deployment", sub: `${counts["DeploymentEvent"] ?? 0} records` },
          ]}
          note="Each stage above is counted from the attestations actually returned by the OTrace service; no linkage between individual rows is implied unless a record carries it."
        />
      </Panel>

      <Panel
        title="OTrace Transaction Log"
        accent="otrace"
        icon={<ListTree className="size-4" />}
        description={
          data
            ? `${filtered.length} of ${records.length} attestations shown · source: GET /trace/search/`
            : "Reading attestations from the OTrace service."
        }
        actions={
          <button
            type="button"
            onClick={() => setNewestFirst((v) => !v)}
            className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-[12.5px] font-medium text-muted-foreground transition-colors hover:bg-secondary"
          >
            <ArrowDownUp className="size-3.5" />
            {newestFirst ? "Newest first" : "Oldest first"}
          </button>
        }
      >
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <FilterSelect
            label="Event Type"
            value={eventFilter}
            onChange={setEventFilter}
            options={eventTypes}
          />
          <FilterSelect
            label="Round"
            value={roundFilter}
            onChange={setRoundFilter}
            options={rounds.map(String)}
          />
          <FilterSelect label="Client / Actor" value={actorFilter} onChange={setActorFilter} options={actors} />
          <label className="relative ml-auto">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search Trace ID"
              className="w-64 rounded-md border border-border bg-card py-2 pl-9 pr-3 text-[13.5px] text-foreground outline-none placeholder:text-muted-foreground focus:border-otrace/50"
            />
          </label>
        </div>

        {error ? (
          <div className="flex items-start gap-3 rounded-md border border-otrace/25 bg-otrace-soft px-4 py-4 text-[13.5px] text-otrace">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <div>
              <div className="font-medium">OTrace log unavailable</div>
              <p className="mt-1 text-muted-foreground">
                {(error as Error).message}. No transactions are shown — this page never substitutes recorded or
                example rows for live attestations.
              </p>
              <p className="mt-1 font-mono text-[12.5px] text-muted-foreground">{TRACE_SEARCH_ENDPOINT}</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="px-1 py-10 text-center text-[13.5px] text-muted-foreground">Loading attestations…</div>
        ) : filtered.length === 0 ? (
          <div className="px-1 py-10 text-center text-[13.5px] text-muted-foreground">
            {records.length === 0
              ? "The OTrace store returned no attestations. Run a traced experiment to generate records."
              : "No records match the current filters."}
          </div>
        ) : (
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-secondary/60 text-[12px] uppercase tracking-wide text-muted-foreground">
                  <Th>Time</Th>
                  <Th>Event Type</Th>
                  <Th>Client / Actor</Th>
                  <Th>Round</Th>
                  <Th>Trace ID</Th>
                  <Th>GDPR Context</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr
                    key={r.traceId}
                    onClick={() => setSelected(r)}
                    className="cursor-pointer border-t border-border/70 text-[13.5px] transition-colors hover:bg-secondary/50"
                  >
                    <Td>
                      <span className="num whitespace-nowrap">{formatTime(r.eventTimestamp ?? r.timestamp)}</span>
                    </Td>
                    <Td>
                      <span className="font-mono text-[12.5px] text-foreground">{r.eventType ?? "—"}</span>
                    </Td>
                    <Td>{r.actor ?? "—"}</Td>
                    <Td>
                      <span className="num">{r.round ?? "—"}</span>
                    </Td>
                    <Td>
                      <span className="num font-mono text-[12px] text-muted-foreground">
                        {r.traceId.slice(0, 8)}…
                      </span>
                    </Td>
                    <Td>
                      <span className="text-[12.5px] text-muted-foreground">
                        {[r.legalBasis, r.gdprArticle].filter(Boolean).join(" · ") || "—"}
                      </span>
                    </Td>
                    <Td>
                      <Chip accent="verified">Recorded</Chip>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length > VISIBLE ? (
              <div className="border-t border-border bg-secondary/40 px-4 py-2.5 text-[12.5px] text-muted-foreground">
                Showing the first {VISIBLE} of {filtered.length} matching attestations. Narrow the filters to see
                more.
              </div>
            ) : null}
          </div>
        )}
      </Panel>

      <Sheet open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          <SheetHeader>
            <SheetTitle>Trace Details</SheetTitle>
            <SheetDescription>
              Every field present in the attestation as returned by the OTrace service.
            </SheetDescription>
          </SheetHeader>
          {selected ? <TraceDetails record={selected} /> : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function TraceDetails({ record }: { record: TraceRecord }) {
  const fields: Array<[string, string | number | undefined]> = [
    ["Trace / attestation ID", record.traceId],
    ["Event type", record.eventType],
    ["Action type", record.actionType],
    ["Round", record.round],
    ["Client / party", record.actor],
    ["Group", record.group],
    ["Operation", record.operation],
    ["Purpose", record.purpose],
    ["Legal basis", record.legalBasis],
    ["Retention period", record.retentionPeriod],
    ["GDPR role", record.gdprRole],
    ["GDPR article", record.gdprArticle],
    ["Data controller", record.dataController],
    ["Consent reference", record.consentReference],
    ["Model version", record.modelVersion],
    ["Event timestamp", record.eventTimestamp],
    ["Attestation timestamp", record.timestamp],
  ];

  return (
    <div className="mt-5 space-y-6 px-1">
      <div>
        {fields.map(([label, value]) => (
          <div
            key={label}
            className="flex items-baseline justify-between gap-6 border-b border-border/70 py-2.5 last:border-0"
          >
            <span className="text-[13px] text-muted-foreground">{label}</span>
            <span className="num break-all text-right font-mono text-[12.5px] text-foreground">
              {value === undefined || value === "" ? "not present in record" : String(value)}
            </span>
          </div>
        ))}
      </div>

      <div>
        <div className="mb-2 text-[13px] font-medium text-foreground">Raw record (JSON)</div>
        <pre className="max-h-96 overflow-auto rounded-md border border-border bg-secondary/50 p-3 font-mono text-[12px] leading-relaxed text-foreground">
          {JSON.stringify(record.raw, null, 2)}
        </pre>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <label className="flex items-center gap-2 text-[12.5px] text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-border bg-card px-2.5 py-1.5 text-[13px] text-foreground outline-none focus:border-otrace/50"
      >
        <option value="all">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-2.5 font-medium">{children}</th>;
}

function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-2.5 align-middle text-foreground">{children}</td>;
}