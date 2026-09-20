import { createFileRoute } from "@tanstack/react-router";
import { Users, Building2, Repeat, Target, Network, Activity, CheckCircle2, Lock } from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import { PageHeader, Panel, StatCard, DataRow, Chip } from "@/components/research/primitives";
import { FederatedArchitecture, RoundTrack, MetricRadar, MetricBar } from "@/components/research/visuals";

export const Route = createFileRoute("/federated-learning")({
  head: () => ({
    meta: [
      { title: "Federated Learning — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Federated setup over 186 eICU hospitals split into 3 clients of 62 hospitals each, trained for 10 FedAvg rounds with secure aggregation.",
      },
      { property: "og:title", content: "Federated Learning — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content: "3 clients, 62 hospitals each, 10 FedAvg rounds with secure aggregation on the eICU sepsis task.",
      },
    ],
  }),
  component: FederatedLearningPage,
});

function FederatedLearningPage() {
  const { data } = useSummary();
  const { federated, dataset, metrics } = data;

  return (
    <div>
      <PageHeader
        title="Federated Learning"
        subtitle="Decentralised training across hospital groups derived from the eICU dataset, recorded end to end by OTrace."
      />

      <div className="mb-7 grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Clients" value={String(federated.clients)} accent="fl" icon={<Users className="size-4" />} />
        <StatCard label="Hospitals" value={String(dataset.hospitals)} accent="fl" icon={<Building2 className="size-4" />} />
        <StatCard label="Rounds" value={String(federated.rounds)} accent="fl" icon={<Repeat className="size-4" />} />
        <StatCard label="Accuracy" value={`${metrics.accuracy}%`} accent="verified" icon={<Target className="size-4" />} />
      </div>

      <Panel
        title="Architecture"
        description="One federated round, end to end. Repeated for the configured number of rounds."
        accent="fl"
        icon={<Network className="size-4" />}
        className="mb-6"
      >
        <FederatedArchitecture
          clients={federated.clients}
          hospitalsPerClient={federated.hospitalsPerClient}
          hospitals={dataset.hospitals}
          stays={dataset.stays}
          rounds={federated.rounds}
          localEpochs={federated.localEpochs}
        />
        <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
          Raw patient data remains local to each client group; only masked model updates are shared, and OTrace
          records the FL lifecycle to support GDPR-aware traceability.
        </p>
      </Panel>

      <div className="mb-6 grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <Panel title="Completed Rounds" accent="fl" icon={<Repeat className="size-4" />}>
          <RoundTrack
            rounds={federated.rounds}
            note="Round-level completion markers only. Per-round accuracy was not recorded in this run, so no learning curve is shown."
          />
        </Panel>

        <Panel title="Privacy Boundary" accent="verified" icon={<Lock className="size-4" />}>
          <div className="grid gap-3 sm:grid-cols-3">
            {Array.from({ length: federated.clients }, (_, i) => (
              <div key={i} className="rounded-md border border-verified/30 bg-verified-soft px-3 py-3 text-center">
                <div className="text-[12.5px] font-semibold text-verified">Client Group {i}</div>
                <div className="num mt-1 text-[18px] font-semibold text-foreground">
                  {federated.hospitalsPerClient}
                </div>
                <div className="text-[11.5px] text-muted-foreground">hospitals · data inside</div>
                <div className="mt-2 rounded-full border border-border bg-card px-2 py-0.5 text-[11px] text-muted-foreground">
                  leaves: updates only
                </div>
              </div>
            ))}
          </div>
          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            Each group holds a disjoint set of hospitals. Records never cross a client boundary; the server observes
            only securely aggregated updates.
          </p>
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Sepsis Prediction Task" accent="fl" icon={<Activity className="size-4" />}>
          <DataRow label="Dataset" value={dataset.name} />
          <DataRow label="ICU stays" value={dataset.stays.toLocaleString()} mono />
          <DataRow label="Features" value={dataset.features} mono />
          <DataRow label="Model" value={federated.model} />
          <DataRow label="Local epochs per round" value={federated.localEpochs} mono />
          <DataRow label="Aggregation" value={<Chip accent="fl">{federated.aggregation}</Chip>} />
          <div className="mt-4 flex items-center gap-2 text-[13px] text-muted-foreground">
            <CheckCircle2 className="size-4 text-verified" />
            {federated.rounds} rounds completed
          </div>
        </Panel>

        <Panel
          title="Test Set Performance"
          accent="verified"
          icon={<Target className="size-4" />}
          description="The five recorded final metrics only — no per-round series."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <MetricRadar
              metrics={[
                { label: "Acc", value: metrics.accuracy },
                { label: "AUC", value: metrics.auc },
                { label: "Prec", value: metrics.precision },
                { label: "Rec", value: metrics.recall },
                { label: "F1", value: metrics.f1 },
              ]}
            />
            <div>
              <MetricBar label="Accuracy" value={metrics.accuracy} display={`${metrics.accuracy}%`} accent="verified" />
              <MetricBar label="AUC" value={metrics.auc} display={`${metrics.auc}%`} accent="verified" />
              <MetricBar label="F1" value={metrics.f1} display={`${metrics.f1.toFixed(1)}%`} accent="fl" />
              <MetricBar label="Precision" value={metrics.precision} display={`${metrics.precision.toFixed(1)}%`} accent="fl" />
              <MetricBar label="Recall" value={metrics.recall} display={`${metrics.recall.toFixed(1)}%`} accent="fl" />
            </div>
          </div>
          <p className="mt-4 text-[13.5px] leading-relaxed text-muted-foreground">
            Released metrics carry differential privacy noise (epsilon {data.privacy.dpEpsilon.toFixed(1)}). The task
            is heavily imbalanced, which is reflected in the precision/recall balance.
          </p>
        </Panel>
      </div>
    </div>
  );
}