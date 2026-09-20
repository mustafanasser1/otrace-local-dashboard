import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { FolderTree, FileCode2, Folder, Play, Cpu, Lock, Route as RouteIcon, FlaskConical, Radio } from "lucide-react";
import { PageHeader, Panel, Chip } from "@/components/research/primitives";
import { IconPipeline } from "@/components/research/visuals";

export const Route = createFileRoute("/source-code")({
  head: () => ({
    meta: [
      { title: "Source Code Explorer — OTrace-FL Research Prototype" },
      {
        name: "description",
        content:
          "Conceptual project tree of the Python backend: federated training, secure aggregation, OTrace event logging, consent and erasure handling, and metamorphic tests.",
      },
      { property: "og:title", content: "Source Code Explorer — OTrace-FL Research Prototype" },
      {
        property: "og:description",
        content: "Plain-language map of the Python/FastAPI federated learning and OTrace codebase.",
      },
    ],
  }),
  component: SourceCodePage,
});

interface Node {
  path: string;
  role: string;
  detail: string;
}

const TREE: { group: string; nodes: Node[] }[] = [
  {
    group: "experiments/",
    nodes: [
      {
        path: "run_traced_experiment.py",
        role: "Entry point for the traced federated run",
        detail:
          "Reads the experiment configuration, builds the client partitions, drives the federated rounds and switches OTrace recording on so that the whole run is captured end to end.",
      },
    ],
  },
  {
    group: "data/",
    nodes: [
      {
        path: "partition_by_hospital.py",
        role: "Hospital-level partitioning of the eICU cohort",
        detail:
          "Groups ICU stays by hospital and assigns hospitals to client groups, giving each client a disjoint set of hospitals so that raw patient data never crosses a client boundary.",
      },
    ],
  },
  {
    group: "federated/",
    nodes: [
      {
        path: "local_training.py",
        role: "Client-side training loop",
        detail:
          "Trains the local model on a client's own data for the configured number of local epochs and returns the resulting model update, never the underlying records.",
      },
      {
        path: "federated_training.py",
        role: "Round orchestration and FedAvg",
        detail:
          "Coordinates the rounds: distribute the global model, collect updates, aggregate them with FedAvg weighting, and hand the new global model to the next round.",
      },
      {
        path: "secure_aggregation.py",
        role: "Masked update aggregation",
        detail:
          "Applies pairwise masks to client updates so that the server can compute the sum without inspecting any individual client contribution; masks cancel out during aggregation.",
      },
      {
        path: "dp_metrics.py",
        role: "Differential privacy on released metrics",
        detail:
          "Adds calibrated noise to the evaluation metrics before they are released, so that published numbers do not leak information about individual records.",
      },
    ],
  },
  {
    group: "otrace/",
    nodes: [
      {
        path: "event_logger.py",
        role: "Lifecycle event recording",
        detail:
          "Creates the trace events (local training, update submission, aggregation, deployment), attaches the GDPR context and the attestation, and writes them to the auditable trace store.",
      },
      {
        path: "consent_manager.py",
        role: "Consent state per pseudonymous subject",
        detail:
          "Holds the current consent state, records withdrawal as an event, and exposes consent status to the training pipeline so that revoked records are not used going forward.",
      },
      {
        path: "erasure_handler.py",
        role: "Erasure impact analysis",
        detail:
          "Given an erasure request, queries the trace store to find which client group and which rounds were influenced by the record and reports whether retraining is required.",
      },
    ],
  },
  {
    group: "otrace-service/",
    nodes: [
      {
        path: "main.py",
        role: "FastAPI application entry point",
        detail:
          "Boots the service, mounts the routers and exposes the summary endpoint that this interface consumes when the backend is reachable.",
      },
      {
        path: "routers/",
        role: "HTTP route modules",
        detail:
          "Group the service endpoints by concern — experiment summary, trace queries, consent operations and erasure impact requests.",
      },
    ],
  },
  {
    group: "tests/",
    nodes: [
      {
        path: "test_metamorphic.py",
        role: "Metamorphic relation test module",
        detail:
          "Holds the test scaffolding for the six defined metamorphic relations, covering client permutation, mask seeds, sample scaling, client splitting, trace event scaling and consent revocation persistence.",
      },
    ],
  },
  {
    group: "streaming/",
    nodes: [
      {
        path: "kafka_producer.py",
        role: "Publishes trace events to Kafka",
        detail:
          "Emits recorded lifecycle events onto a topic so that trace consumption is decoupled from the training process.",
      },
      {
        path: "kafka_consumer.py",
        role: "Consumes and persists trace events",
        detail:
          "Reads events from the topic and stores them in the auditable trace store used for completeness checks and audit queries.",
      },
    ],
  },
];

function SourceCodePage() {
  const [selected, setSelected] = useState<{ group: string; node: Node }>({
    group: TREE[0]!.group,
    node: TREE[0]!.nodes[0]!,
  });

  return (
    <div>
      <PageHeader
        title="Source Code Explorer"
        subtitle="Conceptual map of the existing Python backend. Roles are described in plain language; no source lines are reproduced here."
        right={<Chip accent="neutral">Conceptual view — read only</Chip>}
      />

      <Panel
        title="Pipeline Overview"
        accent="fl"
        icon={<FolderTree className="size-4" />}
        className="mb-5"
        description="How the modules relate, from the entry point to streaming of trace events."
      >
        <IconPipeline
          accent="fl"
          nodes={[
            { icon: <Play className="size-4 text-fl" />, label: "Pipeline", sub: "run_traced_experiment.py" },
            { icon: <Cpu className="size-4 text-fl" />, label: "Training", sub: "local_training · federated_training" },
            { icon: <Lock className="size-4 text-fl" />, label: "Privacy", sub: "secure_aggregation · dp_metrics" },
            { icon: <RouteIcon className="size-4 text-fl" />, label: "OTrace Integration", sub: "event_logger · consent · erasure" },
            { icon: <FlaskConical className="size-4 text-fl" />, label: "Tests", sub: "test_metamorphic.py" },
            { icon: <Radio className="size-4 text-fl" />, label: "Streaming", sub: "kafka producer · consumer" },
          ]}
          note="Module roles are described in plain language; no source lines are reproduced."
        />
      </Panel>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,380px)_1fr]">
        <Panel title="Project Tree" accent="fl" icon={<FolderTree className="size-4" />}>
          <div className="space-y-4">
            {TREE.map((g) => (
              <div key={g.group}>
                <div className="mb-1.5 flex items-center gap-2 text-[13px] font-semibold text-foreground">
                  <Folder className="size-4 text-fl" />
                  <span className="font-mono">{g.group}</span>
                </div>
                <ul className="ml-2 border-l border-border pl-3">
                  {g.nodes.map((n) => {
                    const active = selected.group === g.group && selected.node.path === n.path;
                    return (
                      <li key={g.group + n.path}>
                        <button
                          type="button"
                          onClick={() => setSelected({ group: g.group, node: n })}
                          className={`flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left font-mono text-[13px] transition-colors ${
                            active
                              ? "bg-fl-soft text-fl"
                              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                          }`}
                        >
                          <FileCode2 className="size-3.5 shrink-0" />
                          {n.path}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title={selected.node.path}
          description={selected.node.role}
          accent="otrace"
          icon={<FileCode2 className="size-4" />}
          actions={<Chip accent="neutral">{selected.group.replace("/", "")}</Chip>}
        >
          <p className="text-[14.5px] leading-relaxed text-foreground">{selected.node.detail}</p>
          <div className="mt-5 rounded-md border border-border bg-secondary/40 px-4 py-3">
            <div className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
              Module path
            </div>
            <div className="num mt-1 text-[13.5px] text-foreground">
              {selected.group}
              {selected.node.path}
            </div>
          </div>
          <p className="mt-5 text-[13px] leading-relaxed text-muted-foreground">
            This explorer describes the responsibility of each module so the architecture can be discussed without
            opening the repository. It does not fetch, render or reconstruct the actual source code.
          </p>
        </Panel>
      </div>
    </div>
  );
}