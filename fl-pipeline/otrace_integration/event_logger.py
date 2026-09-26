"""The four federated learning event types, recorded as attestations.

| Event                 | Trigger                                    |
|-----------------------|--------------------------------------------|
| LocalTrainingEvent    | a hospital finishes a local training round |
| UpdateSubmissionEvent | a hospital sends its update to the server  |
| AggregationEvent      | the server averages the received updates   |
| DeploymentEvent       | the trained model is released for use      |

Every event carries the same accountability fields: a consent
reference, the legal basis, the processing purpose, the acting party's
GDPR role, and a timestamp.

Against upstream OTrace two limitations shaped how these were written:
``Action_Type`` offered no federated learning values (gap 1) and
``Party.data_controller`` could not express joint controllership or
processorship (gap 2), which made ``action.information`` the adapter
surface for the whole FL vocabulary. The extended service closes both
gaps - the events attest under their own types and the real roles - and
``config/otrace_config.yaml`` holds the mapping, so pointing this layer
back at an unextended service only takes a config change. The
accountability fields still travel in every payload either way.
"""

import logging
from datetime import datetime, timezone

from otrace_integration.consent_manager import ConsentRegistry
from otrace_integration.otrace_client import OTraceClient, load_otrace_config
from otrace_integration.role_declaration import (
    PartyRole,
    aggregation_server_role,
    hospital_role,
    model_deployer_role,
)

logger = logging.getLogger(__name__)

LOCAL_TRAINING = "LocalTrainingEvent"
UPDATE_SUBMISSION = "UpdateSubmissionEvent"
AGGREGATION = "AggregationEvent"
DEPLOYMENT = "DeploymentEvent"


def _now() -> str:
    """Current UTC time in ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


class FLEventLogger:
    """Records federated learning lifecycle events in OTrace.

    Implements the ``TraceLogger`` protocol the training code expects,
    so attaching it to a run requires no change to the training loop.

    Args:
        client: connected OTrace client.
        consents: registry mapping patients to their consent ids.
        num_groups: number of participating hospital groups.
        config: parsed OTrace configuration.
    """

    def __init__(
        self,
        client: OTraceClient,
        consents: ConsentRegistry,
        num_groups: int,
        config: dict | None = None,
    ):
        self.client = client
        self.consents = consents
        self.config = config or load_otrace_config()
        self.processing = self.config["processing"]
        self.action_types = self.config["event_action_types"]

        self.hospital_roles = {
            group_id: hospital_role(group_id, self.config)
            for group_id in range(num_groups)
        }
        self.server_role = aggregation_server_role(self.config)
        self.deployer_role = model_deployer_role(self.config)

        #: Every attestation id written, in order. The evaluation uses
        #: this to check completeness against expected event counts.
        self.recorded: list[tuple[str, str]] = []

    def _consent_reference(self, group_id: int | None) -> str:
        """A consent id covering the data behind an event.

        A single reference stands for the group's consent set: OTrace
        attestations reference one consent, while a training round
        touches every consenting patient in the group. Representing that
        many-to-one relationship properly needs a schema change, which is
        recorded as a finding rather than worked around here.
        """
        references = list(self.consents.consents.values())
        if not references:
            return "none-on-record"
        if group_id is None:
            return references[0]
        return references[group_id % len(references)]

    def _base_payload(self, event_type: str, role: PartyRole) -> dict:
        """Accountability fields common to every event."""
        return {
            "event_type": event_type,
            "purpose": self.processing["purpose"],
            "legal_basis": self.processing["legal_basis"],
            "retention_period": self.processing["retention_period"],
            "timestamp": _now(),
            **role.as_metadata(),
        }

    def _attest(self, event_type: str, role: PartyRole, payload: dict) -> dict:
        """Write one attestation and remember its id."""
        attestation = self.client.attest(
            party_name=role.party_name,
            data_controller=role.otrace_data_controller,
            action_type=self.action_types[event_type],
            information=payload,
        )
        self.recorded.append((event_type, attestation["id"]))
        logger.debug("%s -> attestation %s", event_type, attestation["id"])
        return attestation

    # -- The four event types --------------------------------------------

    def log_local_training(
        self, group_id: int, server_round: int, metrics: dict
    ) -> dict:
        """A hospital group completed a local training round."""
        role = self.hospital_roles[group_id]
        payload = self._base_payload(LOCAL_TRAINING, role)
        payload.update(
            {
                "hospital_group": group_id,
                "training_round": server_round,
                "local_epochs": metrics.get("epochs"),
                "training_loss": round(float(metrics.get("loss", 0.0)), 6),
                "consent_reference": self._consent_reference(group_id),
                "operation": "train",
            }
        )
        return self._attest(LOCAL_TRAINING, role, payload)

    def log_update_submission(
        self, group_id: int, server_round: int, num_examples: int
    ) -> dict:
        """A hospital group sent model weights to the server.

        This is the point where anything leaves the hospital, so it is
        the event that most needs an accountability record - and the one
        that shows only weights, never records, crossed the boundary.
        """
        role = self.hospital_roles[group_id]
        payload = self._base_payload(UPDATE_SUBMISSION, role)
        payload.update(
            {
                "hospital_group": group_id,
                "training_round": server_round,
                "examples_contributed": num_examples,
                "recipient": self.server_role.party_name,
                "shared_artefact": "model_weights",
                "raw_data_shared": False,
                "consent_reference": self._consent_reference(group_id),
                "operation": "share",
            }
        )
        return self._attest(UPDATE_SUBMISSION, role, payload)

    def log_client_round(
        self,
        group_id: int,
        server_round: int,
        metrics: dict,
        num_examples: int,
    ) -> list[dict]:
        """A hospital group's training and submission, in one batch.

        Local training and update submission happen back to back for the
        same party, so they can share one HTTP request via the service's
        batch endpoint - halving the per-client instrumentation cost
        without changing what gets recorded.
        """
        role = self.hospital_roles[group_id]

        training = self._base_payload(LOCAL_TRAINING, role)
        training.update(
            {
                "hospital_group": group_id,
                "training_round": server_round,
                "local_epochs": metrics.get("epochs"),
                "training_loss": round(float(metrics.get("loss", 0.0)), 6),
                "consent_reference": self._consent_reference(group_id),
                "operation": "train",
            }
        )
        submission = self._base_payload(UPDATE_SUBMISSION, role)
        submission.update(
            {
                "hospital_group": group_id,
                "training_round": server_round,
                "examples_contributed": num_examples,
                "recipient": self.server_role.party_name,
                "shared_artefact": "model_weights",
                "raw_data_shared": False,
                "consent_reference": self._consent_reference(group_id),
                "operation": "share",
            }
        )

        attestations = self.client.attest_batch(
            party_name=role.party_name,
            data_controller=role.otrace_data_controller,
            actions=[
                {"type": self.action_types[LOCAL_TRAINING], "information": training},
                {"type": self.action_types[UPDATE_SUBMISSION], "information": submission},
            ],
        )
        for event_type, attestation in zip(
            (LOCAL_TRAINING, UPDATE_SUBMISSION), attestations
        ):
            self.recorded.append((event_type, attestation["id"]))
            logger.debug("%s -> attestation %s", event_type, attestation["id"])
        return attestations

    def log_aggregation(
        self, server_round: int, num_clients: int, metrics: dict
    ) -> dict:
        """The server averaged the round's client updates."""
        payload = self._base_payload(AGGREGATION, self.server_role)
        payload.update(
            {
                "training_round": server_round,
                "clients_aggregated": num_clients,
                "aggregation_method": metrics.get("aggregation_method", "FedAvg"),
                "total_examples": metrics.get("total_examples"),
                "consent_reference": self._consent_reference(None),
                "operation": "aggregate",
            }
        )
        return self._attest(AGGREGATION, self.server_role, payload)

    def log_deployment(self, model_version: str, metrics: dict) -> dict:
        """The trained global model was released for inference."""
        payload = self._base_payload(DEPLOYMENT, self.deployer_role)
        payload.update(
            {
                "model_version": model_version,
                "model_auc": round(float(metrics.get("auc", 0.0)), 4),
                "model_accuracy": round(float(metrics.get("accuracy", 0.0)), 4),
                "consent_reference": self._consent_reference(None),
                "operation": "deploy",
            }
        )
        return self._attest(DEPLOYMENT, self.deployer_role, payload)

    # -- Reporting --------------------------------------------------------

    def event_counts(self) -> dict[str, int]:
        """How many of each event type were recorded."""
        counts: dict[str, int] = {}
        for event_type, _ in self.recorded:
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts
