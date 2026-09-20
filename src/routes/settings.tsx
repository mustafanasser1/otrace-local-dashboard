import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Settings as SettingsIcon, Plug, Info, RefreshCcw } from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import { API_BASE, DEFAULT_API_BASE, SUMMARY_ENDPOINT } from "@/lib/api";
import { RUN_ENDPOINT } from "@/lib/experiment-run";
import { PageHeader, Panel, DataRow, Chip } from "@/components/research/primitives";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Prototype status: backend connectivity to the FastAPI summary endpoint, data source in use and scope of the interface.",
      },
      { property: "og:title", content: "Settings — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content: "Backend connectivity, data source and scope of the OTrace-FL research prototype interface.",
      },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const { source, error, data, canRun } = useSummary();
  const queryClient = useQueryClient();
  const [testing, setTesting] = useState(false);
  // The connection check only runs in the browser; rendering its outcome before
  // hydration completes would produce a server/client mismatch.
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);

  const testConnection = async () => {
    setTesting(true);
    try {
      await queryClient.refetchQueries({ queryKey: ["otrace", "summary"] });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Status of this prototype interface. Experiment parameters are owned by the Python backend and are not editable here."
      />

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Backend Connection" accent="fl" icon={<Plug className="size-4" />}>
          <DataRow
            label="API base in use"
            value={API_BASE === DEFAULT_API_BASE ? `${API_BASE} (default tunnel — no env override)` : `${API_BASE} (VITE_OTRACE_API_BASE)`}
            mono
          />
          <DataRow label="Summary endpoint" value={SUMMARY_ENDPOINT} mono />
          <DataRow label="Run endpoint" value={RUN_ENDPOINT} mono />
          <DataRow
            label="Current state"
            value={
              !hydrated ? (
                <Chip accent="neutral">Checking…</Chip>
              ) : source === "backend" ? (
                <Chip accent="verified">Live backend</Chip>
              ) : (
                <Chip accent="otrace">Verified fallback (recorded run)</Chip>
              )
            }
          />
          {hydrated && error ? <DataRow label="Last error" value={error} mono /> : null}

          <button
            type="button"
            onClick={testConnection}
            disabled={testing}
            className="mt-4 inline-flex items-center gap-2 rounded-md border border-border bg-card px-3.5 py-2 text-[13.5px] font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-60"
          >
            <RefreshCcw className={`size-4 ${testing ? "animate-spin" : ""}`} />
            {testing ? "Testing connection…" : "Refresh / Test Connection"}
          </button>

          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            When the FastAPI service is reachable, this interface renders its response. Otherwise it falls back to the
            verified values of the recorded run, and every page reports which source is in use.
          </p>
          <div className="mt-3 flex items-start gap-3 rounded-md border border-border bg-secondary/50 px-4 py-3 text-[13.5px] leading-relaxed text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" />
            <span>
              A <code className="font-mono">localhost</code> API base only works when this frontend is run on the same
              machine as FastAPI. The hosted preview runs in your browser against a different origin and cannot reach
              your local machine: it needs an HTTPS-reachable FastAPI URL in{" "}
              <code className="font-mono">VITE_OTRACE_API_BASE</code>, with CORS allowed for the frontend origin.
            </span>
          </div>
        </Panel>


        <Panel title="Prototype Scope" accent="otrace" icon={<SettingsIcon className="size-4" />}>
          <DataRow label="Interface" value="Read-only research prototype" />
          <DataRow label="Experiment endpoint" value={RUN_ENDPOINT} mono />
          <DataRow
            label="Experiment execution"
            value={
              !hydrated ? (
                <Chip accent="neutral">Checking…</Chip>
              ) : canRun ? (
                <Chip accent="verified">Backend advertises run capability</Chip>
              ) : (
                <Chip accent="neutral">Run capability not advertised</Chip>
              )
            }
          />
          <DataRow
            label="Report export"
            value="No backend artifact endpoint; exports are not generated here"
          />
          <DataRow label="Authentication" value="Not part of this prototype" />
          <div className="mt-4 flex items-start gap-3 rounded-md border border-border bg-secondary/50 px-4 py-3 text-[13.5px] leading-relaxed text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" />
            <span>
              Deliberately no production-style controls (users, environments, retention policies) are offered: they
              would suggest capabilities the research prototype does not have.
            </span>
          </div>
        </Panel>

        <Panel title="Research Framing" accent="verified" className="xl:col-span-2">
          <p className="text-[14.5px] leading-relaxed text-foreground">{data.meta.thesisTitle}</p>
          <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">{data.meta.researchQuestion}</p>
          <p className="mt-3 text-[13.5px] leading-relaxed text-muted-foreground">{data.meta.framing}</p>
        </Panel>
      </div>
    </div>
  );
}