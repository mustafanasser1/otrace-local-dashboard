"""Patient consent for federated sepsis training.

Before any hospital trains on a patient's record, that patient must hold
an accepted consent covering the processing. This module establishes
those consents and hands back the references that every subsequent
training event cites as its legal basis.

Patients are identified by their eICU ``uniquepid``. A patient with
stays in more than one hospital still holds a single consent, which is
what makes the erasure path cross-group.
"""

import logging
from dataclasses import dataclass, field

from otrace_integration.otrace_client import OTraceClient, load_otrace_config

logger = logging.getLogger(__name__)


@dataclass
class ConsentRegistry:
    """Consent references for every patient in the federation.

    Attributes:
        consents: patient id to accepted consent id.
        operator: the party the consents are granted to.
    """

    operator: str
    consents: dict[str, str] = field(default_factory=dict)

    def reference_for(self, patient_id: str) -> str | None:
        """The consent id covering a patient, if one exists."""
        return self.consents.get(patient_id)

    def __len__(self) -> int:
        return len(self.consents)


class ConsentManager:
    """Creates and tracks patient consents in OTrace.

    Args:
        client: connected OTrace client.
        config: parsed OTrace configuration.
    """

    def __init__(self, client: OTraceClient, config: dict | None = None):
        self.client = client
        self.config = config or load_otrace_config()
        processing = self.config["processing"]
        self.operator = processing["operator_name"]
        self.data_description = processing["data_description"]
        self.expiry = processing["consent_expiry"]
        self.registry = ConsentRegistry(operator=self.operator)

    def establish_consent(self, patient_id: str) -> str:
        """Offer and accept a consent for one patient.

        Returns:
            The accepted consent's id.
        """
        consent = self.client.offer_consent(
            operator=self.operator,
            user=patient_id,
            data_description=self.data_description,
            operations=["read"],
            expiry_timestamp=self.expiry,
        )
        self.client.accept_consent(consent["id"], patient_id)
        self.registry.consents[patient_id] = consent["id"]
        return consent["id"]

    def establish_all(self, patient_ids: list[str]) -> ConsentRegistry:
        """Establish consents for a list of patients.

        Args:
            patient_ids: eICU ``uniquepid`` values.

        Returns:
            The populated registry.
        """
        for patient_id in patient_ids:
            self.establish_consent(patient_id)
        logger.info(
            "Established %d patient consents with operator %s",
            len(self.registry),
            self.operator,
        )
        return self.registry

    def revoke(self, patient_id: str) -> None:
        """Withdraw a patient's consent (Article 7(3))."""
        consent_id = self.registry.reference_for(patient_id)
        if consent_id is None:
            raise KeyError(f"No consent on record for {patient_id}")
        self.client.revoke_consent(consent_id, patient_id)
        logger.info("Revoked consent %s for %s", consent_id, patient_id)

    def verify_data_use(self, patient_id: str) -> dict:
        """Record a data use for a patient and check it against consent.

        This is the runtime compliance check: it proves a specific use
        of a specific patient's data was permitted by a live consent.

        Returns:
            The service's verdict, with ``valid`` and ``message``.
        """
        consent_id = self.registry.reference_for(patient_id)
        if consent_id is None:
            raise KeyError(f"No consent on record for {patient_id}")

        data_use = self.client.record_data_use(
            operator=self.operator,
            data_description=self.data_description,
            data_subject=patient_id,
            operation_type="read",
            consent_id=consent_id,
        )
        return self.client.check(data_use["id"], consent_id)
