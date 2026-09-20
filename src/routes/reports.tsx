import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { FileText, Info, Download, Database, ListTree, ShieldCheck, FlaskConical } from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import { PageHeader, Panel, DataRow, Chip } from "@/components/research/primitives";

export const Route = createFileRoute("/reports")({
  head: () => ({
    meta: [
      { title: "Reports — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Summaries of the traced federated run: experiment configuration, trace record, compliance modelling and validation design.",
      },
      { property: "og:title", content: "Reports — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content: "Experiment, trace, compliance and validation summaries from the recorded OTrace-FL run.",
      },
    ],
  }),
  component: ReportsPage,
});

function ReportsPage() {
  const { data } = useSummary();
  const [pending, setPending] = useState<string | null>(null);
  const { dataset, federated, trace, metrics, runtime, erasure, metamorphicRelations } = data;

  const reports = [
    {
      id: "experiment",
      title: "Experiment Report",
      desc: "Dataset, federated configuration, privacy settings and final metrics.",
      icon: <Database className="size-4" />,
      accent: "fl" as const,
      facts: [`${federated.clients} clients`, `${federated.rounds} rounds`, `${metrics.accuracy}% accuracy`],
    },
    {
      id: "trace",
      title: "Trace Report",
      desc: "Event counts per type, expected vs actual totals and completeness.",
      icon: <ListTree className="size-4" />,
      accent: "otrace" as const,
      facts: [`${trace.totalEvents}/${trace.expectedEvents} events`, `${trace.completeness}% complete`],
    },
    {
      id: "compliance",
      title: "Compliance Modelling Report",
      desc: "Modelled GDPR articles, consent withdrawal and erasure impact analysis.",
      icon: <ShieldCheck className="size-4" />,
      accent: "fl" as const,
      facts: ["8 articles modelled", `subject ${erasure.pseudonymousPatientId}`, "retraining required"],
    },
    {
      id: "validation",
      title: "Validation Report",
      desc: "Runtime overhead measurements and the six defined metamorphic relations.",
      icon: <FlaskConical className="size-4" />,
      accent: "verified" as const,
      facts: [`+${runtime.increaseSec.toFixed(2)} sec (+${runtime.increasePercent.toFixed(1)}%)`, `${metamorphicRelations.length} relations defined`],
    },
  ];

  return (
    <div>
      <PageHeader
        title="Reports"
        subtitle="Readable summaries of the recorded run. Export is produced by the Python backend and is not connected to this interface."
      />

      <div className="mb-6 grid gap-5 lg:grid-cols-2">
        {reports.map((r) => (
          <Panel key={r.id} title={r.title} description={r.desc} accent={r.accent} icon={r.icon}>
            <div className="mb-4 flex flex-wrap gap-2">
              {r.facts.map((f) => (
                <Chip key={f} accent={r.accent}>
                  {f}
                </Chip>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setPending(r.id)}
                className="inline-flex items-center gap-2 rounded-md border border-border bg-secondary px-3.5 py-2 text-[13.5px] font-medium text-secondary-foreground transition-colors hover:bg-accent"
              >
                <Download className="size-4" />
                Export PDF
              </button>
              <Chip accent="neutral">Export integration unavailable</Chip>
            </div>
            {pending === r.id ? (
              <div className="mt-4 flex items-start gap-3 rounded-md border border-otrace/25 bg-otrace-soft px-4 py-3 text-[13.5px] leading-relaxed text-otrace">
                <Info className="mt-0.5 size-4 shrink-0" />
                <span>
                  No file was generated. Report export is not wired to the FastAPI backend yet, so this action is a
                  placeholder rather than a download.
                </span>
              </div>
            ) : null}
          </Panel>
        ))}
      </div>

      <Panel title="Summary at a Glance" accent="verified" icon={<FileText className="size-4" />}>
        <div className="grid gap-8 lg:grid-cols-3">
          <div>
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">Setup</h3>
            <DataRow label="Dataset" value={dataset.name} />
            <DataRow label="Stays / features" value={`${dataset.stays.toLocaleString()} / ${dataset.features}`} mono />
            <DataRow label="Hospitals" value={dataset.hospitals} mono />
            <DataRow
              label="Federation"
              value={`${federated.clients} clients × ${federated.hospitalsPerClient} hospitals`}
            />
            <DataRow label="Rounds / epochs" value={`${federated.rounds} / ${federated.localEpochs}`} mono />
          </div>
          <div>
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">Results</h3>
            <DataRow label="Accuracy / AUC" value={`${metrics.accuracy}% / ${metrics.auc}%`} mono />
            <DataRow label="F1" value={`${metrics.f1.toFixed(1)}%`} mono />
            <DataRow label="Trace events" value={`${trace.totalEvents} / ${trace.expectedEvents}`} mono />
            <DataRow label="Completeness" value={`${trace.completeness}%`} mono />
            <DataRow
              label="Overhead"
              value={`+${runtime.increaseSec.toFixed(2)} sec (+${runtime.increasePercent.toFixed(1)}%)`}
              mono
            />
          </div>
          <div>
            <h3 className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
              Compliance & validation
            </h3>
            <DataRow label="Erasure subject" value={erasure.pseudonymousPatientId} mono />
            <DataRow label="Affected rounds" value={erasure.affectedRounds} mono />
            <DataRow label="Retraining" value="Required" />
            <DataRow label="Metamorphic relations" value={`${metamorphicRelations.length} defined`} />
            <DataRow label="Claim scope" value="GDPR-aware traceability support" />
          </div>
        </div>
      </Panel>
    </div>
  );
}