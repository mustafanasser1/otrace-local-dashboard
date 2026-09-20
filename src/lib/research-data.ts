/**
 * Verified experiment data for the OTrace-FL Research Prototype.
 *
 * These values are used as structured FALLBACK data, shown only when the
 * existing Python/FastAPI backend endpoint (`/ui/api/summary`) is unavailable.
 * They must not be altered: every number here comes from the recorded run.
 */

export type ComplianceStatus = "addressed" | "partially-addressed";

export interface ExperimentSummary {
  meta: {
    projectName: string;
    thesisTitle: string;
    researchQuestion: string;
    framing: string;
    status: string;
  };
  dataset: {
    name: string;
    stays: number;
    features: number;
    hospitals: number;
    task: string;
  };
  federated: {
    clients: number;
    hospitalsPerClient: number;
    rounds: number;
    localEpochs: number;
    aggregation: string;
    model: string;
  };
  privacy: {
    secureAggregation: boolean;
    differentialPrivacyOnReleasedMetrics: boolean;
    otraceRecording: boolean;
    gdprContext: boolean;
    dpEpsilon: number;
  };
  metrics: {
    accuracy: number;
    auc: number;
    f1: number;
    precision: number;
    recall: number;
  };
  trace: {
    localTrainingEvents: number;
    updateSubmissionEvents: number;
    aggregationEvents: number;
    deploymentEvents: number;
    totalEvents: number;
    expectedEvents: number;
    completeness: number;
  };
  erasure: {
    pseudonymousPatientId: string;
    consentState: string;
    affectedGroup: number;
    affectedRounds: number;
    retrainingRequired: boolean;
    liveConsentRemaining: boolean;
  };
  runtime: {
    withoutTracingSec: number;
    withTracingSec: number;
    increaseSec: number;
    increasePercent: number;
    perAttestationMs: number;
  };
  metamorphicRelations: { id: string; name: string; description: string }[];
  gdprArticles: {
    article: string;
    title: string;
    status: ComplianceStatus;
    note: string;
  }[];
  /**
   * Optional capability advertisement from the FastAPI backend.
   * Absent in the verified fallback: the prototype must not assume a run
   * endpoint exists unless the live backend says so.
   */
  capabilities?: {
    run?: boolean;
  };
}

export const FALLBACK_SUMMARY: ExperimentSummary = {
  meta: {
    projectName: "OTrace-FL Research Prototype",
    thesisTitle:
      "Modelado y validación de modelos GDPR en sistemas distribuidos, utilizando testing e Inteligencia Artificial.",
    researchQuestion:
      "How can GDPR compliance be modelled in distributed AI systems, and how can it be validated?",
    framing:
      "OTrace is one initial experimental strand of the thesis, not the whole thesis. The prototype supports GDPR-aware traceability, accountability and compliance validation; it does not claim full GDPR compliance.",
    status: "System Ready",
  },
  dataset: {
    name: "eICU Collaborative Research Database",
    stays: 1627,
    features: 74,
    hospitals: 186,
    task: "Sepsis prediction (binary classification)",
  },
  federated: {
    clients: 3,
    hospitalsPerClient: 62,
    rounds: 10,
    localEpochs: 3,
    aggregation: "FedAvg",
    model: "Simple Neural Network",
  },
  privacy: {
    secureAggregation: true,
    differentialPrivacyOnReleasedMetrics: true,
    otraceRecording: true,
    gdprContext: true,
    dpEpsilon: 5.0,
  },
  metrics: {
    accuracy: 70.4,
    auc: 67.8,
    f1: 36.0,
    precision: 27.0,
    recall: 54.0,
  },
  trace: {
    localTrainingEvents: 30,
    updateSubmissionEvents: 30,
    aggregationEvents: 10,
    deploymentEvents: 1,
    totalEvents: 71,
    expectedEvents: 71,
    completeness: 100,
  },
  erasure: {
    pseudonymousPatientId: "002-10009",
    consentState: "Consent revoked",
    affectedGroup: 0,
    affectedRounds: 10,
    retrainingRequired: true,
    liveConsentRemaining: false,
  },
  runtime: {
    withoutTracingSec: 5.73,
    withTracingSec: 6.19,
    increaseSec: 0.46,
    increasePercent: 8.0,
    perAttestationMs: 6.5,
  },
  metamorphicRelations: [
    {
      id: "MR1",
      name: "Client permutation invariance",
      description:
        "Reordering the participating clients should not change the aggregated global model or the recorded trace semantics.",
    },
    {
      id: "MR2",
      name: "Secure aggregation mask seed invariance",
      description:
        "Changing the random mask seeds used by secure aggregation should leave the aggregated result unchanged.",
    },
    {
      id: "MR3",
      name: "Uniform sample-count scaling",
      description:
        "Scaling every client's sample count by the same factor should leave FedAvg weighting, and therefore the global model, unchanged.",
    },
    {
      id: "MR4",
      name: "Client splitting invariance",
      description:
        "Splitting one client into two clients holding disjoint halves of its data should preserve the weighted aggregate.",
    },
    {
      id: "MR5",
      name: "Trace event scaling with rounds",
      description:
        "The number of recorded trace events should scale predictably with the configured number of federated rounds.",
    },
    {
      id: "MR6",
      name: "Consent revocation persistence",
      description:
        "Once consent is revoked, the revocation must persist across subsequent rounds and remain visible in the auditable trace store.",
    },
  ],
  gdprArticles: [
    {
      article: "Art. 5",
      title: "Principles relating to processing",
      status: "partially-addressed",
      note: "Purpose limitation and accountability are represented in the GDPR context attached to each recorded event.",
    },
    {
      article: "Art. 6",
      title: "Lawfulness of processing",
      status: "partially-addressed",
      note: "A legal basis field is modelled per processing event; validation of the basis itself remains out of scope.",
    },
    {
      article: "Art. 7",
      title: "Conditions for consent (incl. withdrawal)",
      status: "addressed",
      note: "Consent state and withdrawal are modelled by the consent manager; withdrawal is recorded as a first-class event.",
    },
    {
      article: "Art. 9",
      title: "Special categories of personal data",
      status: "partially-addressed",
      note: "Health data is flagged in the GDPR context; safeguards are represented, not enforced end to end.",
    },
    {
      article: "Art. 17",
      title: "Right to erasure",
      status: "partially-addressed",
      note: "Erasure impact analysis identifies affected client groups and rounds and reports whether retraining is required.",
    },
    {
      article: "Art. 25",
      title: "Data protection by design and by default",
      status: "partially-addressed",
      note: "Raw patient data remains local; secure aggregation and DP on released metrics are enabled by configuration.",
    },
    {
      article: "Art. 30",
      title: "Records of processing activities",
      status: "addressed",
      note: "The auditable trace store provides a structured, queryable record of federated processing activities.",
    },
    {
      article: "Art. 32",
      title: "Security of processing",
      status: "partially-addressed",
      note: "Secure aggregation and differential privacy on released metrics are applied; broader security controls are out of scope.",
    },
  ],
};