# OTrace-FL

GDPR-traceable federated learning, end to end: a sepsis prediction
model trained across three simulated hospital consortia on the eICU
demo dataset, with every step of the training lifecycle recorded as
attestations in an extended OTrace service — under secure aggregation,
with differentially private metric release, streamable through Kafka,
and validated by a metamorphic test suite.

Part of the thesis *"Modelado y validación de modelos GDPR en sistemas
distribuidos, utilizando testing e Inteligencia Artificial."*

## Contents

| Directory | What it is |
|---|---|
| `otrace-service/` | The OTrace consent and traceability service (Python/FastAPI, SQLite), extended for FL: the four FL lifecycle events as first-class action types, joint controller (Art. 26) and processor (Art. 28) roles, consent-state-specific `/check` reasons, batch attestations. |
| `fl-pipeline/` | eICU preprocessing, the sepsis model, centralised baseline, federated training (Flower FedAvg) with pairwise-masking secure aggregation and OpenDP differential privacy on released metrics, the OTrace integration layer, the Kafka streamed producer/consumer pipeline (docker-compose included), two end-to-end experiments, and the test suites (92 + 31 tests, including six metamorphic relations). |

## Quick start

Read **"OTrace-FL — How to Run and Demo"** (alongside this package).
It covers setup, the eICU data download, the Kafka broker, and four
demonstrations:

1. The OTrace service alone
2. Federated learning alone (secure aggregation + DP on by default)
3. The integrated, fully traced experiment
4. The streamed pipeline: train → Kafka → enrich → attest → replay

## The four FL event types

| Event | Trigger | Recorded as |
|---|---|---|
| LocalTrainingEvent | A hospital completes a local training round | native `local training` action |
| UpdateSubmissionEvent | A hospital sends its update to the server | native `update submission` action |
| AggregationEvent | The server aggregates client updates | native `aggregation` action |
| DeploymentEvent | The model is deployed for inference | native `deployment` action |

Every event carries the consent reference, legal basis, purpose, and
data-controller role of the acting party.

## GDPR roles in the scenario

- Hospital consortia — joint controllers (Article 26), attested natively
- Aggregation server — processor (Article 28), attested natively
- Model deployer — controller (Article 24)

## Scope

The classifier is deliberately a small baseline model: the contribution
is the traceability and validation layer, not the ML. Secure
aggregation simulates pairwise key agreement with a configured seed (no
dropout recovery), and differential privacy applies to released
metrics/queries, not the training loop — both simplifications are
documented where they live. The metamorphic suite
(`fl-pipeline/tests/test_metamorphic.py`) is the first concrete
instance of the research plan's Specific Objective 6.
