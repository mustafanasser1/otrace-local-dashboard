"""Thin REST client for the OTrace service.

One method per endpoint the FL pipeline needs, with the request shapes
that the running v0.5 service actually expects. Several differ from what
the OpenAPI document alone suggests, so they are noted where relevant:

* ``expiry_timestamp`` on a consent offer is a query parameter
* consent operations are objects (``{"operation_type": "read"}``), not
  bare strings
* accepting a consent requires a ``User`` body naming the data subject
* DSR request fields are query parameters and ``request_type`` is a
  fixed enum
"""

import logging
from pathlib import Path
from typing import Any

import requests
import yaml

logger = logging.getLogger(__name__)

FL_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
OTRACE_CONFIG_PATH = FL_PIPELINE_ROOT / "config" / "otrace_config.yaml"

#: DSR request types the service accepts.
DSR_ACCESS = "Access Request"
DSR_CORRECTION = "Correction Request"
DSR_DELETE = "Delete Request"
DSR_OUTPUT = "Output Request"


def load_otrace_config(path: str | Path = OTRACE_CONFIG_PATH) -> dict:
    """Read the OTrace integration configuration."""
    with open(path) as fh:
        return yaml.safe_load(fh)


class OTraceUnavailableError(RuntimeError):
    """Raised when the OTrace service cannot be reached."""


class OTraceClient:
    """REST wrapper around a running OTrace service.

    Args:
        config: parsed OTrace configuration. Loaded from the default
            path when omitted.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or load_otrace_config()
        service = self.config["service"]
        self.base_url = service["base_url"].rstrip("/")
        self.timeout = service["timeout_seconds"]

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Send one request and return the decoded JSON body."""
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method, url, timeout=self.timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise OTraceUnavailableError(
                f"OTrace service unreachable at {self.base_url}. "
                "Start it with: python -m uvicorn main:app --port 8080"
            ) from exc

        if not response.ok:
            raise OTraceUnavailableError(
                f"{method} {path} returned {response.status_code}: {response.text[:200]}"
            )
        return response.json()

    def is_available(self) -> bool:
        """True when the service answers its root endpoint."""
        try:
            self._request("GET", "/")
            return True
        except OTraceUnavailableError:
            return False

    # -- Attestations ----------------------------------------------------

    def attest(
        self,
        party_name: str,
        data_controller: str,
        action_type: str,
        information: dict,
    ) -> dict:
        """Record an attestation for a party's action.

        ``information`` is a freeform object, which is where all
        federated learning metadata travels: OTrace's Action_Type enum
        has no FL values of its own.
        """
        return self._request(
            "POST",
            f"/attestations/attest/{party_name}/{data_controller}/",
            json={"type": action_type, "information": information},
        )

    def attest_batch(
        self,
        party_name: str,
        data_controller: str,
        actions: list[dict],
    ) -> list[dict]:
        """Record several attestations for one party in a single request.

        Each item in ``actions`` is ``{"type": ..., "information": ...}``.
        One HTTP round-trip per event is the dominant instrumentation
        cost, so events that occur together should be posted together.
        """
        return self._request(
            "POST",
            f"/attestations/attest_batch/{party_name}/{data_controller}/",
            json=actions,
        )

    def get_attestations(self, party_name: str) -> list[dict]:
        """Every attestation recorded for a party."""
        return self._request("GET", f"/attestations/{party_name}/all/")

    # -- Consent ---------------------------------------------------------

    def offer_consent(
        self,
        operator: str,
        user: str,
        data_description: str,
        operations: list[str],
        expiry_timestamp: str,
    ) -> dict:
        """Offer a consent to a data subject, returning the consent record."""
        return self._request(
            "POST",
            "/consents/offer/",
            params={"expiry_timestamp": expiry_timestamp},
            json={
                "operator": {"name": operator},
                "user": {"name": user},
                "data": {"description": data_description},
                "operations": [{"operation_type": op} for op in operations],
            },
        )

    def accept_consent(self, consent_id: str, user: str) -> dict:
        """Accept a previously offered consent on behalf of the subject."""
        return self._request(
            "POST", f"/consents/accept/{consent_id}/", json={"name": user}
        )

    def revoke_consent(self, consent_id: str, user: str) -> dict:
        """Withdraw a consent (GDPR Article 7(3))."""
        return self._request(
            "POST", f"/consents/revoke/{consent_id}/", json={"name": user}
        )

    def get_consent(self, consent_id: str) -> dict:
        """Fetch a single consent record."""
        return self._request("GET", f"/consents/{consent_id}/")

    def list_consents(self, user: str) -> list[dict]:
        """Every consent belonging to a data subject."""
        return self._request("GET", f"/consents/list/{user}/")

    # -- Data use --------------------------------------------------------

    def record_data_use(
        self,
        operator: str,
        data_description: str,
        data_subject: str,
        operation_type: str,
        consent_id: str,
    ) -> dict:
        """Record an actual use of personal data under a consent."""
        return self._request(
            "POST",
            "/data_use/use/",
            json={
                "operator": {"name": operator},
                "data": {"description": data_description},
                "data_subject": {"name": data_subject},
                "operation": {"operation_type": operation_type},
                "basis": {"base_type": "consent", "basis_object": consent_id},
            },
        )

    def check(self, data_use_id: str, consent_id: str) -> dict:
        """Verify a data use was permitted by a consent.

        Returns a mapping with ``valid`` and an explanatory ``message``.
        """
        return self._request("GET", f"/check/{data_use_id}/{consent_id}")

    # -- Data subject rights ---------------------------------------------

    def make_dsr(self, subject: str, controller: str, request_type: str) -> dict:
        """Raise a data subject request against a controller."""
        return self._request(
            "POST",
            "/dsr/request/",
            params={
                "subject": subject,
                "controller": controller,
                "request_type": request_type,
            },
        )

    def get_dsr(self, request_id: str) -> dict:
        """Fetch a data subject request by id."""
        return self._request("GET", f"/dsr/request/{request_id}")

    def update_dsr_status(self, request_id: str, status: str) -> dict:
        """Move a data subject request to a new status."""
        return self._request(
            "PUT", f"/dsr/request/{request_id}/status", params={"status": status}
        )
