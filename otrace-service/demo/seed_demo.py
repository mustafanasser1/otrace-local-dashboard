"""Scripted GDPR walkthrough against a running OTrace service.

Plays the hospital consent story end to end, one labelled step at a
time, so a live demonstration is repeatable rather than typed by hand at
a terminal. Each step prints the request it makes and the answer it gets
back, and names the GDPR article it exercises.

The scenario mirrors the federated sepsis experiment: a patient consents
to their ICU data being used for research, a hospital trains on it, the
use is checked against the consent, the patient later withdraws consent,
and the same check then fails.

Usage::

    # against the default service on port 8080
    python demo/seed_demo.py

    # or a different one
    python demo/seed_demo.py --base-url http://127.0.0.1:9000
"""

import argparse
import json
import sys
import time
import uuid

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8080"

#: Pause between steps so a live audience can follow along.
DEFAULT_STEP_PAUSE = 0.0


class DemoError(RuntimeError):
    """Raised when the service answers a demo step unexpectedly."""


class Demo:
    """Runs the walkthrough against one service.

    Args:
        base_url: root URL of the running OTrace service.
        pause: seconds to wait between steps.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, pause: float = DEFAULT_STEP_PAUSE):
        self.base_url = base_url.rstrip("/")
        self.pause = pause
        self.step_number = 0
        # A run tag keeps repeated demos from colliding in one database.
        self.tag = uuid.uuid4().hex[:6]
        self.hospital = f"st-marys-hospital-{self.tag}"
        self.consortium = f"sepsis-research-consortium-{self.tag}"
        self.patient = f"patient-{self.tag}"

    # -- presentation helpers --------------------------------------------

    def step(self, title: str, article: str = "") -> None:
        self.step_number += 1
        suffix = f"   [{article}]" if article else ""
        print(f"\n\033[1mSTEP {self.step_number}: {title}\033[0m{suffix}")
        print("-" * 72)
        time.sleep(self.pause)

    @staticmethod
    def show(label: str, value) -> None:
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, indent=2)
            if len(rendered) > 600:
                rendered = rendered[:600] + "\n  ... truncated"
            print(f"  {label}:\n{_indent(rendered)}")
        else:
            print(f"  {label}: {value}")

    def call(self, method: str, path: str, **kwargs):
        """Make a request, showing what was sent, and return the body."""
        print(f"  -> {method} {path}")
        response = requests.request(
            method, f"{self.base_url}{path}", timeout=10, **kwargs
        )
        if not response.ok:
            raise DemoError(f"{method} {path} -> {response.status_code}: {response.text[:200]}")
        return response.json()

    # -- the walkthrough --------------------------------------------------

    def run(self) -> None:
        print("=" * 72)
        print("  OTrace GDPR walkthrough - federated sepsis research scenario")
        print("=" * 72)
        print(f"  Service:    {self.base_url}")
        print(f"  Hospital:   {self.hospital}")
        print(f"  Controller: {self.consortium}")
        print(f"  Patient:    {self.patient}")

        consent_id = self.offer_and_accept_consent()
        self.record_and_check_use(consent_id, expect_valid=True)
        self.attest_training()
        self.inspect_trail()
        self.withdraw_consent(consent_id)
        self.record_and_check_use(consent_id, expect_valid=False)
        self.raise_erasure_request()

        print("\n" + "=" * 72)
        print("  Walkthrough complete. Every step above is stored in OTrace.")
        print("=" * 72 + "\n")

    def offer_and_accept_consent(self) -> str:
        self.step("The consortium offers the patient a consent", "Article 6, 7")
        consent = self.call(
            "POST",
            "/consents/offer/",
            params={"expiry_timestamp": "2030-01-01T00:00:00"},
            json={
                "operator": {"name": self.consortium},
                "user": {"name": self.patient},
                "data": {"description": "ICU vital signs, laboratory results"},
                "operations": [{"operation_type": "read"}],
            },
        )
        self.show("consent id", consent["id"])
        self.show("state", consent["state"])

        self.step("The patient accepts", "Article 7")
        accepted = self.call(
            "POST",
            f"/consents/accept/{consent['id']}/",
            json={"name": self.patient},
        )
        self.show("state", accepted["state"])
        return consent["id"]

    def record_and_check_use(self, consent_id: str, expect_valid: bool) -> None:
        label = (
            "The hospital reads the patient's data and the use is checked"
            if expect_valid
            else "The hospital attempts the same use again after withdrawal"
        )
        self.step(label, "Article 5(2) accountability")
        data_use = self.call(
            "POST",
            "/data_use/use/",
            json={
                "operator": {"name": self.consortium},
                "data": {"description": "ICU vital signs, laboratory results"},
                "data_subject": {"name": self.patient},
                "operation": {"operation_type": "read"},
                "basis": {"base_type": "consent", "basis_object": consent_id},
            },
        )
        verdict = self.call("GET", f"/check/{data_use['id']}/{consent_id}")
        self.show("valid", verdict["valid"])
        self.show("message", verdict["message"])

        if verdict["valid"] is not expect_valid:
            raise DemoError(
                f"Expected valid={expect_valid} but the service said {verdict['valid']}"
            )
        if not expect_valid:
            print("\n  \033[1mThis is the point of the walkthrough:\033[0m the same "
                  "request that\n  succeeded earlier is now refused, because consent "
                  "was withdrawn.")

    def attest_training(self) -> None:
        self.step("The hospital attests a federated training round", "Article 30")
        print("  OTrace has no federated-learning action type, so the event is")
        print("  filed under 'data use' with its real name in action.information.")
        attestation = self.call(
            "POST",
            f"/attestations/attest/{self.hospital}/data_provider/",
            json={
                "type": "data use",
                "information": {
                    "event_type": "LocalTrainingEvent",
                    "training_round": 1,
                    "purpose": "Training a sepsis prediction model",
                    "legal_basis": "consent",
                    "data_controller_role": "joint_controller",
                    "gdpr_article": "Article 26",
                    "raw_data_shared": False,
                },
            },
        )
        self.show("attestation", attestation)

    def inspect_trail(self) -> None:
        self.step("A reviewer reads back the hospital's attestations", "Article 5(2)")
        trail = self.call("GET", f"/attestations/{self.hospital}/all/")
        self.show("attestations recorded", len(trail))
        for record in trail:
            information = record["action"]["information"]
            print(
                f"    - {information.get('event_type')} "
                f"round {information.get('training_round')} "
                f"as {information.get('data_controller_role')}"
            )

    def withdraw_consent(self, consent_id: str) -> None:
        self.step("The patient withdraws consent", "Article 7(3)")
        revoked = self.call(
            "POST",
            f"/consents/revoke/{consent_id}/",
            json={"name": self.patient},
        )
        self.show("state", revoked["state"])

    def raise_erasure_request(self) -> None:
        self.step("The patient exercises the right to erasure", "Article 17")
        request = self.call(
            "POST",
            "/dsr/request/",
            params={
                "subject": self.patient,
                "controller": self.consortium,
                "request_type": "Delete Request",
            },
        )
        self.show("request id", request["request_id"])
        self.show("status", request["status"])

        completed = self.call(
            "PUT",
            f"/dsr/request/{request['request_id']}/status",
            params={"status": "Completed"},
        )
        self.show("status after handling", completed.get("status", "Completed"))
        print("\n  Note: records and consent can be erased, but a model already")
        print("  trained on this patient still carries their averaged contribution.")
        print("  The attestation trail above is what tells a controller which")
        print("  rounds were affected.")


def _indent(text: str, spaces: int = 4) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_STEP_PAUSE,
        help="seconds between steps, for live presentation",
    )
    args = parser.parse_args()

    demo = Demo(base_url=args.base_url, pause=args.pause)
    try:
        demo.run()
    except requests.RequestException:
        print(
            f"\nCould not reach the OTrace service at {args.base_url}.\n"
            "Start it first:\n"
            "  cd otrace-service && python -m uvicorn main:app --port 8080\n",
            file=sys.stderr,
        )
        return 1
    except DemoError as exc:
        print(f"\nDemo failed: {exc}\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
