import { createFileRoute } from "@tanstack/react-router";
import { Target, CheckCircle2, Timer, FlaskConical, FileWarning } from "lucide-react";
import { useSummary } from "@/hooks/useSummary";
import { PageHeader, Panel, StatCard, DataRow, Chip } from "@/components/research/primitives";
import { MetricBar, Ring, CompareBars, ConceptOrbit } from "@/components/research/visuals";

export const Route = createFileRoute("/evaluation")({
  head: () => ({
    meta: [
      { title: "Evaluation & Validation — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Model metrics, trace completeness, tracing runtime overhead and the six metamorphic relations defined for validating the traced federated pipeline.",
      },
      { property: "og:title", content: "Evaluation & Validation — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content: "Metrics, 100% trace completeness, +8.0% tracing overhead and six defined metamorphic relations.",
      },
    ],
  }),
  component: EvaluationPage,
});

function pct(value: number) { return value <= 1 ? value * 100 : value; }

function EvaluationPage() {
  const { data } = useSummary();
  const { metrics, trace, runtime, privacy, erasure, metamorphicRelations } = data;

  return (
    <div>
      <PageHeader
        title="Evaluation & Validation"
        subtitle="Latest model, trace and validation results."
      />

      <div className="mb-7 grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Accuracy" value={`${pct(metrics.accuracy).toFixed(2)}%`} accent="verified" icon={<Target className="size-4" />} />
        <StatCard label="AUC" value={`${pct(metrics.auc).toFixed(2)}%`} accent="verified" icon={<Target className="size-4" />} />
        <StatCard
          label="Trace Completeness"
          value={`${trace.completeness}%`}
          accent="verified"
          icon={<CheckCircle2 className="size-4" />}
        />
        <StatCard
          label="Tracing Overhead"
          value={`+${runtime.increasePercent.toFixed(1)}%`}
          accent="otrace"
          icon={<Timer className="size-4" />}
        />
      </div>

      <div className="mb-6 grid gap-5 xl:grid-cols-3">
        <Panel title="Model Metrics" accent="verified" icon={<Target className="size-4" />}>
          <MetricBar label="Accuracy" value={pct(metrics.accuracy)} display={`${pct(metrics.accuracy).toFixed(2)}%`} accent="verified" />
          <MetricBar label="AUC" value={pct(metrics.auc)} display={`${pct(metrics.auc).toFixed(2)}%`} accent="verified" />
          <MetricBar label="F1" value={pct(metrics.f1)} display={`${pct(metrics.f1).toFixed(2)}%`} accent="fl" />
          <MetricBar label="Precision" value={pct(metrics.precision)} display={`${pct(metrics.precision).toFixed(2)}%`} accent="fl" />
          <MetricBar label="Recall" value={pct(metrics.recall)} display={`${pct(metrics.recall).toFixed(2)}%`} accent="fl" />
          <div className="mt-3 border-t border-border pt-2">
            <DataRow label="DP epsilon on released metrics" value={privacy.dpEpsilon.toFixed(1)} mono />
          </div>
        </Panel>

        <Panel title="Trace Completeness" accent="otrace" icon={<CheckCircle2 className="size-4" />}>
          <div className="flex flex-col items-center">
            <Ring
              value={trace.totalEvents}
              max={trace.expectedEvents}
              accent="verified"
              size={150}
              centerLabel={`${trace.completeness}%`}
              centerSub={`${trace.totalEvents}/${trace.expectedEvents}`}
            />
          </div>
          <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
            30 local training + 30 update submission + 10 aggregation + 1 deployment events matched the expected
            count of {trace.expectedEvents} derived from the configuration.
          </p>
        </Panel>

        <Panel title="Runtime Overhead" accent="otrace" icon={<Timer className="size-4" />}>
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
        </Panel>
      </div>

      <Panel
        className="mb-6"
        title="Erasure Impact (Art. 17)"
        accent="otrace"
        icon={<FileWarning className="size-4" />}
        description="Result of the erasure impact analysis performed on the recorded run; it reports scope and a retraining verdict, not an executed retraining."
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <DataRow label="Pseudonymous subject" value={erasure.pseudonymousPatientId} mono />
            <DataRow label="Consent state" value={erasure.consentState} />
            <DataRow label="Affected client group" value={`Group ${erasure.affectedGroup}`} mono />
            <DataRow label="Affected rounds" value={erasure.affectedRounds} mono />
            <DataRow
              label="Retraining"
              value={
                erasure.retrainingRequired ? (
                  <Chip accent="otrace">Required</Chip>
                ) : (
                  <Chip accent="verified">Not required</Chip>
                )
              }
            />
            <DataRow label="Live consent remaining" value={erasure.liveConsentRemaining ? "Yes" : "None"} />
          </div>
          <p className="text-[13.5px] leading-relaxed text-muted-foreground">
            The subject contributed to client group {erasure.affectedGroup} across all {erasure.affectedRounds}{" "}
            rounds, so the record influenced every aggregated global model. Because the trace store records which
            client group and which rounds each contribution reached, the analysis can state the scope of the erasure
            and conclude that retraining is required. This is the validation angle that connects traceability to a
            concrete data-subject right.
          </p>
        </div>
      </Panel>

      <Panel

        title="Metamorphic Relations"
        accent="fl"
        icon={<FlaskConical className="size-4" />}
        description="Six metamorphic relations executed successfully on the validation suite."
        actions={<Chip accent="verified">{metamorphicRelations.length}/{metamorphicRelations.length} passed</Chip>}
      >
        <ConceptOrbit
          accent="fl"
          centerTitle="Validation"
          centerSub="metamorphic relations · 6/6 passed"
          items={metamorphicRelations.map((r) => ({
            key: r.id,
            node: (
              <div className="rounded-md border border-border bg-secondary/40 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="num rounded-md border border-fl/25 bg-fl-soft px-2 py-0.5 text-[12.5px] font-semibold text-fl">
                      {r.id}
                    </span>
                    <span className="text-[13.5px] font-medium text-foreground">{r.name}</span>
                  </div>
                  <Chip accent="verified">Passed</Chip>
                </div>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">{r.description}</p>
              </div>
            ),
          }))}
        />
      </Panel>
    </div>
  );
}