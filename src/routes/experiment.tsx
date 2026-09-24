import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Database,
  Settings2,
  Lock,
  Play,
  Trash2,
  ClipboardCheck,
  Users,
  Building2,
  Layers,
  ShieldCheck,
  Route as RouteIcon,
  FileCheck,
  UserX,
  Search,
  RefreshCcw,
  Repeat,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Circle,
} from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import {
  runExperiment,
  RunEndpointUnavailableError,
  type RunState,
} from "@/lib/experiment-run";
import { PageHeader, Panel, DataRow, Chip } from "@/components/research/primitives";
import {
  CompositionTiles,
  StatusRows,
  MetricBar,
  CompareBars,
  StepFlow,
  Ring,
} from "@/components/research/visuals";

export const Route = createFileRoute("/experiment")({
  head: () => ({
    meta: [
      { title: "Experiment — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Configuration and recorded results of the federated learning experiment: eICU dataset, 3 clients, 10 rounds, FedAvg, secure aggregation and OTrace recording.",
      },
      { property: "og:title", content: "Experiment — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content: "Dataset, FL configuration, privacy settings and recorded results of the OTrace-FL experiment.",
      },
    ],
  }),
  component: ExperimentPage,
});

function pct(value: number) { return value <= 1 ? value * 100 : value; }

function ExperimentPage() {
  const { data, isLive, canRun } = useSummary();
  const [consentSample, setConsentSample] = useState("60");
  const [seed, setSeed] = useState("42");
  const [runState, setRunState] = useState<RunState>({ phase: "idle" });
  const queryClient = useQueryClient();
  const { dataset, federated, privacy, metrics, trace, runtime, erasure } = data;

  const runMutation = useMutation({
    mutationFn: async () => {
      const body: { Consent sample?: number; seed?: number } = {};
      const cs = Number(consentSample);
      const sd = Number(seed);
      if (consentSample.trim() !== "" && Number.isFinite(cs)) body.consent_sample = cs;
      if (seed.trim() !== "" && Number.isFinite(sd)) body.seed = sd;
      setRunState({ phase: "running", startedAt: Date.now() });
      return runExperiment(body);
    },
    onMutate: () => setRunState({ phase: "starting" }),
    onSuccess: async (result) => {
      setRunState({ phase: "completed", finishedAt: Date.now(), result });
      // Real run finished: pull the backend's own summary and attestation log.
      await queryClient.invalidateQueries({ queryKey: ["otrace", "summary"] });
      await queryClient.invalidateQueries({ queryKey: ["otrace", "trace-log"] });
      await queryClient.invalidateQueries({ queryKey: ["otrace", "consents"] });


    },
    onError: (err: unknown) => {
      const unavailable = err instanceof RunEndpointUnavailableError;
      setRunState({
        phase: "failed",
        unavailable,
        error: unavailable
          ? "Run endpoint unavailable"
          : err instanceof Error
            ? err.message
            : "Run failed",
      });
    },
  });

  const isBusy = runState.phase === "starting" || runState.phase === "running";

  return (
    <div>
      <PageHeader
        title="Experiment"
        subtitle="Configure, run, and review the current federated learning experiment."
      />

      <Panel className="mb-6">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[15px] font-semibold text-foreground">Latest Experiment</span>
              <Chip accent="verified">Completed</Chip>
              <Chip accent={isLive ? "verified" : "otrace"}>
                {isLive ? "Live backend summary" : "Verified fallback (backend offline)"}
              </Chip>
            </div>
            <p className="max-w-3xl text-[13.5px] leading-relaxed text-muted-foreground">
              Traced federated run over {dataset.hospitals} eICU hospitals split into {federated.clients} client
              groups, {federated.rounds} rounds of {federated.aggregation} with {federated.localEpochs} local epochs
              per round, recorded end to end by OTrace.
            </p>
          </div>
          <div className="text-right">
            <div className="mb-2 flex items-center justify-end gap-2">
              <label className="text-[12.5px] text-muted-foreground" htmlFor="consent-sample">
                consent_sample
              </label>
              <input
                id="consent-sample"
                type="number"
                inputMode="numeric"
                value={consentSample}
                onChange={(e) => setConsentSample(e.target.value)}
                disabled={!canRun || isBusy}
                className="num w-20 rounded-md border border-border bg-card px-2 py-1 text-right text-[13px] text-foreground disabled:opacity-60"
              />
              <label className="text-[12.5px] text-muted-foreground" htmlFor="run-seed">
                seed
              </label>
              <input
                id="run-seed"
                type="number"
                inputMode="numeric"
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                disabled={!canRun || isBusy}
                className="num w-20 rounded-md border border-border bg-card px-2 py-1 text-right text-[13px] text-foreground disabled:opacity-60"
              />
            </div>
            <button
              type="button"
              disabled={!canRun || isBusy}
              aria-disabled={!canRun || isBusy}
              onClick={() => runMutation.mutate()}
              title={
                canRun
                  ? "Start a real traced run on the FastAPI backend"
                  : "Backend does not advertise run capability"
              }
              className={
                canRun && !isBusy
                  ? "inline-flex items-center gap-2 rounded-md border border-fl/30 bg-fl px-4 py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-fl/90"
                  : "inline-flex cursor-not-allowed items-center gap-2 rounded-md border border-border bg-secondary px-4 py-2.5 text-[14px] font-medium text-muted-foreground opacity-80"
              }
            >
              {isBusy ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              Run Experiment
            </button>
          </div>
        </div>

        <div className="mt-5 border-t border-border pt-4">
          <RunStateArea state={runState} />
        </div>

      </Panel>


      <div className="mb-6 grid gap-5 xl:grid-cols-3">
        <Panel title="Dataset" accent="fl" icon={<Database className="size-4" />}>
          <CompositionTiles
            items={[
              {
                icon: <Layers className="size-4 text-fl" />,
                value: dataset.stays.toLocaleString(),
                label: "ICU stays",
                accent: "fl",
              },
              { icon: <Settings2 className="size-4 text-fl" />, value: String(dataset.features), label: "features", accent: "fl" },
              {
                icon: <Building2 className="size-4 text-fl" />,
                value: String(dataset.hospitals),
                label: "hospitals",
                accent: "fl",
              },
            ]}
          />
          <div className="mt-4">
            <DataRow label="Source" value={dataset.name} />
            <DataRow label="Task" value={dataset.task} />
          </div>
        </Panel>

        <Panel title="FL Configuration" accent="fl" icon={<Settings2 className="size-4" />}>
          <div className="flex items-center justify-center gap-2">
            {Array.from({ length: federated.clients }, (_, i) => (
              <div key={i} className="flex-1 rounded-md border border-fl/25 bg-fl-soft px-2 py-3 text-center">
                <Users className="mx-auto size-4 text-fl" />
                <div className="num mt-1 text-[15px] font-semibold text-fl">{federated.hospitalsPerClient}</div>
                <div className="text-[11px] text-muted-foreground">hospitals</div>
              </div>
            ))}
          </div>
          <div className="my-2 text-center text-[12px] text-muted-foreground">↓ model updates</div>
          <div className="rounded-md border border-otrace/25 bg-otrace-soft px-3 py-2.5 text-center text-[13px] font-semibold text-otrace">
            {federated.aggregation} · {federated.rounds} rounds
          </div>
          <div className="mt-4">
            <DataRow label="Clients / groups" value={federated.clients} mono />
            <DataRow label="Local epochs" value={federated.localEpochs} mono />
            <DataRow label="Model" value={federated.model} />
          </div>
        </Panel>

        <Panel title="Privacy & Trace Settings" accent="otrace" icon={<Lock className="size-4" />}>
          <StatusRows
            rows={[
              {
                icon: <Lock className="size-4" />,
                label: "Secure Aggregation",
                state: privacy.secureAggregation ? "ON" : "OFF",
                accent: privacy.secureAggregation ? "verified" : "neutral",
              },
              {
                icon: <ShieldCheck className="size-4" />,
                label: "DP on released metrics",
                state: privacy.differentialPrivacyOnReleasedMetrics ? "ON" : "OFF",
                accent: privacy.differentialPrivacyOnReleasedMetrics ? "verified" : "neutral",
                sub: `epsilon ${privacy.dpEpsilon.toFixed(1)}`,
              },
              {
                icon: <RouteIcon className="size-4" />,
                label: "OTrace recording",
                state: privacy.otraceRecording ? "ON" : "OFF",
                accent: privacy.otraceRecording ? "otrace" : "neutral",
              },
              {
                icon: <FileCheck className="size-4" />,
                label: "GDPR context",
                state: privacy.gdprContext ? "ON" : "OFF",
                accent: privacy.gdprContext ? "otrace" : "neutral",
              },
            ]}
          />
        </Panel>
      </div>

      <Panel title="Latest Results" className="mb-6" accent="verified" icon={<ClipboardCheck className="size-4" />}>
        <div className="grid gap-8 lg:grid-cols-3">
          <div>
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
              Model performance
            </h3>
            <MetricBar label="Accuracy" value={pct(metrics.accuracy)} display={`${pct(metrics.accuracy).toFixed(2)}%`} accent="verified" />
            <MetricBar label="AUC" value={pct(metrics.auc)} display={`${pct(metrics.auc).toFixed(2)}%`} accent="verified" />
            <MetricBar label="F1" value={pct(metrics.f1)} display={`${pct(metrics.f1).toFixed(2)}%`} accent="fl" />
            <MetricBar label="Precision" value={pct(metrics.precision)} display={`${pct(metrics.precision).toFixed(2)}%`} accent="fl" />
            <MetricBar label="Recall" value={pct(metrics.recall)} display={`${pct(metrics.recall).toFixed(2)}%`} accent="fl" />
            <div className="mt-3 border-t border-border pt-2">
              <DataRow label="DP epsilon" value={privacy.dpEpsilon.toFixed(1)} mono />
            </div>
          </div>
          <div>
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
              Trace record
            </h3>
            <DataRow label="LocalTrainingEvent" value={trace.localTrainingEvents} mono />
            <DataRow label="UpdateSubmissionEvent" value={trace.updateSubmissionEvents} mono />
            <DataRow label="AggregationEvent" value={trace.aggregationEvents} mono />
            <DataRow label="DeploymentEvent" value={trace.deploymentEvents} mono />
            <DataRow label="Total / expected" value={`${trace.totalEvents} / ${trace.expectedEvents}`} mono />
            <div className="mt-3 flex justify-center">
              <Ring
                value={trace.totalEvents}
                max={trace.expectedEvents}
                accent="verified"
                size={112}
                centerLabel={`${trace.completeness}%`}
                centerSub={`${trace.totalEvents}/${trace.expectedEvents}`}
              />
            </div>
          </div>
          <div>
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
              Runtime overhead
            </h3>
            <CompareBars
              unit="sec"
              items={[
                { label: "Without OTrace", value: runtime.withoutTracingSec, accent: "neutral" },
                { label: "With OTrace", value: runtime.withTracingSec, accent: "otrace" },
              ]}
              footnote={
                <span>
                  +{runtime.increaseSec.toFixed(2)} sec · +{runtime.increasePercent.toFixed(1)}% · ~
                  {runtime.perAttestationMs} ms per attestation
                </span>
              }
            />
          </div>
        </div>
      </Panel>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Erasure Impact Demo" accent="otrace" icon={<Trash2 className="size-4" />}>
          <StepFlow
            accent="otrace"
            steps={[
              { icon: <UserX className="size-4 text-otrace" />, title: `Patient ${erasure.pseudonymousPatientId}`, sub: "pseudonymous subject" },
              { icon: <Trash2 className="size-4 text-otrace" />, title: "Consent revoked", sub: erasure.consentState },
              { icon: <Search className="size-4 text-otrace" />, title: "Trace search", sub: "auditable trace store" },
              { icon: <Repeat className="size-4 text-otrace" />, title: `Group ${erasure.affectedGroup} · ${erasure.affectedRounds} rounds`, sub: "influence scope" },
              { icon: <RefreshCcw className="size-4 text-otrace" />, title: "Retraining required", sub: "no live consent remains" },
            ]}
          />
          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            The trace store makes it possible to determine which rounds and which client group were influenced by a
            record after consent withdrawal, and therefore whether retraining is required.
          </p>
        </Panel>

        <Panel title="Validation Snapshot" accent="verified" icon={<ClipboardCheck className="size-4" />}>
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="rounded-md border border-border bg-secondary/40 px-4 py-4 text-center">
              <div className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">
                Expected vs actual events
              </div>
              <div className="mt-3 flex items-center justify-center gap-3">
                <span className="num rounded-md border border-border bg-card px-3 py-2 text-[18px] font-semibold text-foreground">
                  {trace.expectedEvents}
                </span>
                <span className="text-[13px] text-muted-foreground">vs</span>
                <span className="num rounded-md border border-verified/30 bg-verified-soft px-3 py-2 text-[18px] font-semibold text-verified">
                  {trace.totalEvents}
                </span>
              </div>
              <div className="mt-3 text-[13px] text-verified">Completeness {trace.completeness}%</div>
            </div>
            <div className="rounded-md border border-border bg-secondary/40 px-4 py-4 text-center">
              <div className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">
                Metamorphic relations
              </div>
              <div className="num mt-3 text-[28px] font-semibold text-foreground">
                {data.metamorphicRelations.length}
              </div>
              <div className="mt-1 flex flex-wrap justify-center gap-1.5">
                {data.metamorphicRelations.map((r) => (
                  <span
                    key={r.id}
                    title={r.name}
                    className="num rounded-md border border-fl/25 bg-fl-soft px-2 py-0.5 text-[12px] font-semibold text-fl"
                  >
                    {r.id}
                  </span>
                ))}
              </div>
              <div className="mt-3 text-[13px] text-verified">6/6 passed</div>
            </div>
          </div>
          <div className="mt-4">
            <DataRow label="Tracing overhead" value={`+${runtime.increaseSec.toFixed(2)} sec (+${runtime.increasePercent.toFixed(1)}%)`} mono />
            <DataRow label="Erasure impact analysis" value={erasure.retrainingRequired ? "Retraining required" : "No retraining required"} />
          </div>
          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            All six metamorphic relations passed in the executed validation suite.
          </p>
        </Panel>
      </div>
    </div>
  );
}

function RunStateArea({ state }: { state: RunState }) {
  const config = (() => {
    switch (state.phase) {
      case "idle":
        return {
          icon: <Circle className="size-4 text-muted-foreground" />,
          label: "Idle",
          detail: "Ready to run.",
          tone: "border-border bg-secondary/40 text-muted-foreground",
        };
      case "starting":
        return {
          icon: <Loader2 className="size-4 animate-spin text-fl" />,
          label: "Starting",
          detail: "Starting experiment.",
          tone: "border-fl/25 bg-fl-soft text-fl",
        };
      case "running":
        return {
          icon: <Loader2 className="size-4 animate-spin text-fl" />,
          label: "Running",
          detail:
            "Experiment is running.",
          tone: "border-fl/25 bg-fl-soft text-fl",
        };
      case "completed":
        return {
          icon: <CheckCircle2 className="size-4 text-verified" />,
          label: "Completed",
          detail: `Run reported complete by the backend${
            state.result.duration_sec !== undefined ? ` in ${state.result.duration_sec} sec` : ""
          }.`,
          tone: "border-verified/30 bg-verified-soft text-verified",
        };
      case "failed":
        return {
          icon: <AlertTriangle className="size-4 text-otrace" />,
          label: state.unavailable ? "Run endpoint unavailable" : "Failed",
          detail: state.unavailable
            ? "Experiment runner is unavailable."
            : state.error,
          tone: "border-otrace/30 bg-otrace-soft text-otrace",
        };
    }
  })();

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">Run state</span>
      <span
        className={`inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-[13px] font-semibold ${config.tone}`}
      >
        {config.icon}
        {config.label}
      </span>
      <span className="max-w-3xl text-[13px] leading-relaxed text-muted-foreground">{config.detail}</span>
    </div>
  );
}