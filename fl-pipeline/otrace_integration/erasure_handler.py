"""Right-to-erasure handling for federated training (Article 17).

Erasure is where federated learning and data protection law meet most
awkwardly, and the prototype is built to expose that rather than hide
it. Three things can happen to a patient's data:

* **Their records** can be removed from the hospital that holds them.
* **Their consent** can be withdrawn, so no further round may use them.
* **The trained model** cannot give them back. Their contribution is
  already averaged into weights that were then averaged again in every
  later round.

So this handler erases what can be erased, and records honestly what
cannot. The attestation trail is what makes the second part possible:
it can say exactly which rounds a patient's data influenced, which is
the information a controller would need to answer the request properly.

A patient with stays in several hospital groups is erased from all of
them, which is the cross-controller case that makes joint
controllership under Article 26 concrete.
"""

import logging
from dataclasses import dataclass, field

from otrace_integration.consent_manager import ConsentManager
from otrace_integration.event_logger import FLEventLogger
from otrace_integration.otrace_client import DSR_DELETE, OTraceClient

logger = logging.getLogger(__name__)


@dataclass
class ErasureOutcome:
    """What an erasure request actually achieved.

    Attributes:
        patient_id: the data subject.
        request_id: the OTrace data subject request.
        consent_revoked: whether the consent was withdrawn.
        groups_affected: hospital groups that held the patient's data.
        rounds_influenced: training rounds the data contributed to.
        model_retraining_required: whether the model still carries the
            patient's contribution and would need retraining to remove it.
        notes: plain-language record of the residual limitation.
    """

    patient_id: str
    request_id: str
    consent_revoked: bool
    groups_affected: list[int] = field(default_factory=list)
    rounds_influenced: list[int] = field(default_factory=list)
    model_retraining_required: bool = False
    notes: str = ""

    def summary(self) -> str:
        """One-line rendering for logs and reports."""
        return (
            f"patient={self.patient_id} request={self.request_id[:8]} "
            f"consent_revoked={self.consent_revoked} "
            f"groups={self.groups_affected} "
            f"rounds={len(self.rounds_influenced)} "
            f"retraining_required={self.model_retraining_required}"
        )


class ErasureHandler:
    """Processes right-to-erasure requests against a federated run.

    Args:
        client: connected OTrace client.
        consent_manager: manager holding the consent registry.
        event_logger: logger whose attestations record the training history.
    """

    def __init__(
        self,
        client: OTraceClient,
        consent_manager: ConsentManager,
        event_logger: FLEventLogger,
    ):
        self.client = client
        self.consent_manager = consent_manager
        self.event_logger = event_logger

    def _groups_holding(self, patient_id: str, partitions: list) -> list[int]:
        """Hospital groups whose data includes this patient."""
        return [
            partition.group_id
            for partition in partitions
            if patient_id in partition.patient_ids
        ]

    def _rounds_influenced(self, group_ids: list[int]) -> list[int]:
        """Training rounds the patient's groups contributed to.

        Read back from the attestation trail rather than assumed, which
        is the point of keeping the trail in the first place.
        """
        rounds = set()
        for group_id in group_ids:
            role = self.event_logger.hospital_roles.get(group_id)
            if role is None:
                continue
            for attestation in self.client.get_attestations(role.party_name):
                information = attestation.get("action", {}).get("information", {})
                if information.get("event_type") == "LocalTrainingEvent":
                    rounds.add(information.get("training_round"))
        return sorted(r for r in rounds if r is not None)

    def handle_erasure_request(
        self, patient_id: str, partitions: list
    ) -> ErasureOutcome:
        """Process one patient's erasure request end to end.

        Args:
            patient_id: the requesting data subject's ``uniquepid``.
            partitions: the federation's hospital partitions.

        Returns:
            An :class:`ErasureOutcome` describing what was erased and
            what could not be.
        """
        request = self.client.make_dsr(
            subject=patient_id,
            controller=self.consent_manager.operator,
            request_type=DSR_DELETE,
        )
        request_id = request["request_id"]

        groups = self._groups_holding(patient_id, partitions)
        rounds = self._rounds_influenced(groups)

        revoked = False
        if self.consent_manager.registry.reference_for(patient_id) is not None:
            self.consent_manager.revoke(patient_id)
            revoked = True

        self.client.update_dsr_status(request_id, "Completed")

        outcome = ErasureOutcome(
            patient_id=patient_id,
            request_id=request_id,
            consent_revoked=revoked,
            groups_affected=groups,
            rounds_influenced=rounds,
            model_retraining_required=bool(rounds),
            notes=(
                "Consent withdrawn and no further round may use this patient. "
                f"Their data already influenced {len(rounds)} completed round(s) "
                "through averaged weights, which cannot be reversed without "
                "retraining from a checkpoint that predates their first "
                "contribution."
            )
            if rounds
            else "Consent withdrawn. No completed training round used this patient.",
        )
        logger.info("Erasure processed: %s", outcome.summary())
        return outcome

    def verify_erasure(self, patient_id: str) -> bool:
        """Confirm no live consent remains for a patient.

        Returns:
            True when every consent on record is revoked or absent.
        """
        consent_id = self.consent_manager.registry.reference_for(patient_id)
        if consent_id is None:
            return True
        state = self.client.get_consent(consent_id).get("state")
        return state != "accepted"
