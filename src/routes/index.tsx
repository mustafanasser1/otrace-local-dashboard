import { createFileRoute } from "@tanstack/react-router";
import {
  Users,
  Building2,
  Repeat,
  ListTree,
  CheckCircle2,
  Target,
  Network,
  Route as RouteIcon,
  Activity,
  ShieldCheck,
  FileCheck,
  Database,
} from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import { PageHeader, Panel, StatCard, Chip } from "@/components/research/primitives";
import { FederatedMiniDiagram, IconPipeline, Ring } from "@/components/research/visuals";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Overview of the federated learning run on eICU data with OTrace-based GDPR-aware traceability: 3 clients, 10 rounds, 71 trace events.",
      },
      { property: "og:title", content: "Dashboard — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content:
          "Federated learning on eICU with OTrace traceability: 3 clients, 10 rounds, 71 recorded trace events, 100% completeness.",
      },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const { data } = useSummary();
  const { federated, trace, metrics, runtime, erasure, meta } = data;

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={meta.researchQuestion}
      />

      <div className="panel mb-7 px-6 py-5">
        <div className="flex flex-wrap items-center gap-2">
          <Chip accent="fl">Thesis</Chip>
          <Chip accent="otrace">OTrace: one initial experimental strand</Chip>
        </div>
        <p className="mt-3 text-[14.5px] leading-relaxed text-foreground">{meta.thesisTitle}</p>
        <p className="mt-2 max-w-4xl text-[13.5px] leading-relaxed text-muted-foreground">
          {meta.framing}
        </p>
      </div>

      <div className="mb-7 grid grid-cols-2 gap-4 xl:grid-cols-6">
        <StatCard label="Clients" value={String(federated.clients)} accent="fl" icon={<Users className="size-4" />} />
        <StatCard
          label="Hospitals / Client"
          value={String(federated.hospitalsPerClient)}
          accent="fl"
          icon={<Building2 className="size-4" />}
        />
        <StatCard label="Rounds" value={String(federated.rounds)} accent="fl" icon={<Repeat className="size-4" />} />
        <StatCard
          label="Trace Events"
          value={String(trace.totalEvents)}
          accent="otrace"
          icon={<ListTree className="size-4" />}
        />
        <StatCard
          label="Trace Completeness"
          value={`${trace.completeness}%`}
          accent="verified"
          icon={<CheckCircle2 className="size-4" />}
        />
        <StatCard
          label="Last Accuracy"
          value={`${metrics.accuracy}%`}
          accent="verified"
          icon={<Target className="size-4" />}
        />
      </div>

      <div className="mb-7 grid gap-5 xl:grid-cols-2">
        <Panel
          title="Federated Learning"
          description="Decentralised training across three hospital groups derived from the eICU dataset."
          accent="fl"
          icon={<Network className="size-4" />}
        >
          <FederatedMiniDiagram clients={federated.clients} hospitalsPerClient={federated.hospitalsPerClient} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Chip accent="verified">Raw patient data stays local</Chip>
            <Chip accent="fl">FedAvg · secure aggregation</Chip>
          </div>
          <p className="mt-3 text-[13.5px] leading-relaxed text-muted-foreground">
            Only model updates leave each client group; aggregation uses secure aggregation with FedAvg weighting.
          </p>
        </Panel>

        <Panel
          title="OTrace Integration"
          description="Every federated lifecycle step is recorded with GDPR context and an attestation."
          accent="otrace"
          icon={<RouteIcon className="size-4" />}
        >
          <IconPipeline
            accent="otrace"
            nodes={[
              { icon: <Activity className="size-4 text-otrace" />, label: "FL Event", sub: "training · update · aggregation" },
              { icon: <ShieldCheck className="size-4 text-otrace" />, label: "GDPR Context", sub: "purpose · basis · consent" },
              { icon: <FileCheck className="size-4 text-otrace" />, label: "Attestation", sub: `~${runtime.perAttestationMs} ms` },
              { icon: <Database className="size-4 text-otrace" />, label: "Auditable Trace Store", sub: `${trace.totalEvents} records` },
            ]}
            note="The resulting records support GDPR-aware traceability, accountability and compliance validation; they do not by themselves establish full GDPR compliance."
          />
        </Panel>
      </div>

      <div className="flex justify-center">
        <div className="w-full max-w-5xl">
          <Panel title="Evaluation Summary" accent="verified" icon={<CheckCircle2 className="size-4" />}>
            <div className="grid items-center gap-6 lg:grid-cols-[auto_1fr]">
              <Ring
                value={trace.totalEvents}
                max={trace.expectedEvents}
                accent="verified"
                centerLabel={`${trace.completeness}%`}
                centerSub={`${trace.totalEvents}/${trace.expectedEvents} events`}
                caption="Trace completeness"
              />
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                <SummaryTile label="Accuracy" value={`${metrics.accuracy}%`} />
                <SummaryTile label="Trace" value={`${trace.completeness}%`} hint={`${trace.totalEvents}/${trace.expectedEvents}`} />
                <SummaryTile
                  label="Overhead"
                  value={`+${runtime.increasePercent.toFixed(1)}%`}
                  hint={`+${runtime.increaseSec.toFixed(2)} sec`}
                />
                <SummaryTile label="Metamorphic Relations" value={`${data.metamorphicRelations.length}`} hint="Defined" />
                <SummaryTile
                  label="Erasure Impact"
                  value={erasure.retrainingRequired ? "Retraining" : "None"}
                  hint={erasure.retrainingRequired ? "Required" : undefined}
                />
              </div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function SummaryTile({ label, value, hint }: { label: string; value: string; hint?: string | undefined }) {
  return (
    <div className="rounded-md border border-border bg-secondary/50 px-4 py-4 text-center">
      <div className="text-[12px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="num mt-2 text-[22px] font-semibold text-foreground">{value}</div>
      {hint ? <div className="mt-1 text-[12.5px] text-muted-foreground">{hint}</div> : null}
    </div>
  );
}