"""Tests for the OTrace integration layer.

Unit tests run against a fake client so they need no running service.
Tests marked with ``otrace`` exercise the real one and are skipped when
it is not up.
"""

import pytest

from otrace_integration.consent_manager import ConsentManager, ConsentRegistry
from otrace_integration.erasure_handler import ErasureHandler
from otrace_integration.event_logger import (
    AGGREGATION,
    DEPLOYMENT,
    LOCAL_TRAINING,
    UPDATE_SUBMISSION,
    FLEventLogger,
)
from otrace_integration.otrace_client import (
    DSR_DELETE,
    OTraceClient,
    load_otrace_config,
)
from otrace_integration.role_declaration import (
    aggregation_server_role,
    declare_all_roles,
    hospital_role,
    model_deployer_role,
)


class FakeOTraceClient:
    """In-memory stand-in recording every call the layer makes."""

    def __init__(self):
        self.attestations: list[dict] = []
        self.consents: dict[str, dict] = {}
        self.data_uses: list[dict] = []
        self.dsrs: dict[str, dict] = {}
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:04d}"

    def attest(self, party_name, data_controller, action_type, information):
        record = {
            "id": self._next_id("att"),
            "party": {"name": party_name, "data_controller": data_controller},
            "action": {"type": action_type, "information": information},
        }
        self.attestations.append(record)
        return record

    def attest_batch(self, party_name, data_controller, actions):
        self.batch_calls = getattr(self, "batch_calls", 0) + 1
        return [
            self.attest(
                party_name, data_controller, action["type"], action["information"]
            )
            for action in actions
        ]

    def get_attestations(self, party_name):
        return [
            a for a in self.attestations if a["party"]["name"] == party_name
        ]

    def offer_consent(self, operator, user, data_description, operations, expiry_timestamp):
        record = {"id": self._next_id("con"), "user": {"name": user}, "state": "offered"}
        self.consents[record["id"]] = record
        return record

    def accept_consent(self, consent_id, user):
        self.consents[consent_id]["state"] = "accepted"
        return self.consents[consent_id]

    def revoke_consent(self, consent_id, user):
        self.consents[consent_id]["state"] = "revoked"
        return self.consents[consent_id]

    def get_consent(self, consent_id):
        return self.consents[consent_id]

    def record_data_use(self, operator, data_description, data_subject, operation_type, consent_id):
        record = {"id": self._next_id("use"), "consent": consent_id}
        self.data_uses.append(record)
        return record

    def check(self, data_use_id, consent_id):
        accepted = self.consents.get(consent_id, {}).get("state") == "accepted"
        return {"valid": accepted, "message": "ok" if accepted else "not accepted"}

    def make_dsr(self, subject, controller, request_type):
        record = {
            "request_id": self._next_id("dsr"),
            "status": "Received",
            "subject": subject,
            "type": request_type,
        }
        self.dsrs[record["request_id"]] = record
        return record

    def update_dsr_status(self, request_id, status):
        self.dsrs[request_id]["status"] = status
        return self.dsrs[request_id]


class FakePartition:
    def __init__(self, group_id: int, patient_ids: list[str]):
        self.group_id = group_id
        self.patient_ids = patient_ids


@pytest.fixture
def client() -> FakeOTraceClient:
    return FakeOTraceClient()


@pytest.fixture
def config() -> dict:
    return load_otrace_config()


@pytest.fixture
def registry(client, config) -> ConsentRegistry:
    return ConsentManager(client, config).establish_all(["pt-a", "pt-b", "pt-c"])


# -- Roles ---------------------------------------------------------------


def test_hospitals_are_joint_controllers(config):
    role = hospital_role(0, config)
    assert role.gdpr_role == "joint_controller"
    assert role.gdpr_article == "Article 26"
    assert role.party_name == "hospital-group-0"


def test_server_is_processor_and_deployer_is_controller(config):
    assert aggregation_server_role(config).gdpr_role == "processor"
    assert model_deployer_role(config).gdpr_role == "controller"


def test_extended_roles_are_native(config):
    """The extended service closes the role gap for the two FL roles.

    Upstream OTrace admits only consumer/data_provider/data_recipient,
    so hospitals and the server used to attest under the closest value.
    Against the extended service both attest under their real role. The
    deployer still maps to ``consumer``: upstream has no plain
    ``controller`` value and the extension adds only what the FL
    scenario cannot express at all.
    """
    assert hospital_role(0, config).otrace_data_controller == "joint_controller"
    assert aggregation_server_role(config).otrace_data_controller == "processor"
    deployer = model_deployer_role(config)
    assert deployer.otrace_data_controller == "consumer"
    assert deployer.otrace_data_controller != deployer.gdpr_role


def test_declare_all_roles_covers_every_party(config):
    roles = declare_all_roles(3, config)
    assert len(roles) == 5
    assert sum(r.gdpr_role == "joint_controller" for r in roles) == 3
    assert len({r.party_name for r in roles}) == 5


# -- Consent -------------------------------------------------------------


def test_establish_all_accepts_every_consent(client, config):
    registry = ConsentManager(client, config).establish_all(["pt-a", "pt-b"])
    assert len(registry) == 2
    assert all(c["state"] == "accepted" for c in client.consents.values())


def test_verify_data_use_passes_for_a_consenting_patient(client, config):
    manager = ConsentManager(client, config)
    manager.establish_all(["pt-a"])
    assert manager.verify_data_use("pt-a")["valid"] is True


def test_verify_data_use_fails_after_revocation(client, config):
    manager = ConsentManager(client, config)
    manager.establish_all(["pt-a"])
    manager.revoke("pt-a")
    assert manager.verify_data_use("pt-a")["valid"] is False


def test_unknown_patient_raises(client, config):
    manager = ConsentManager(client, config)
    with pytest.raises(KeyError):
        manager.verify_data_use("nobody")


# -- Event logging -------------------------------------------------------


def test_each_event_type_writes_one_attestation(client, registry, config):
    log = FLEventLogger(client, registry, num_groups=3, config=config)
    log.log_local_training(0, 1, {"loss": 0.4, "epochs": 3})
    log.log_update_submission(0, 1, 422)
    log.log_aggregation(1, 3, {"total_examples": 1282})
    log.log_deployment("v1", {"auc": 0.75, "accuracy": 0.75})

    assert log.event_counts() == {
        LOCAL_TRAINING: 1,
        UPDATE_SUBMISSION: 1,
        AGGREGATION: 1,
        DEPLOYMENT: 1,
    }
    assert len(client.attestations) == 4


@pytest.mark.parametrize(
    "call",
    [
        lambda log: log.log_local_training(0, 1, {"loss": 0.4, "epochs": 3}),
        lambda log: log.log_update_submission(0, 1, 100),
        lambda log: log.log_aggregation(1, 3, {"total_examples": 900}),
        lambda log: log.log_deployment("v1", {"auc": 0.7, "accuracy": 0.7}),
    ],
)
def test_every_event_carries_the_accountability_fields(
    client, registry, config, call
):
    """The five fields the thesis requires on every event."""
    log = FLEventLogger(client, registry, num_groups=3, config=config)
    call(log)
    information = client.attestations[-1]["action"]["information"]

    for field in (
        "consent_reference",
        "legal_basis",
        "purpose",
        "data_controller_role",
        "timestamp",
    ):
        assert information.get(field), f"missing {field}"


def test_fl_events_attest_under_their_own_types(client, registry, config):
    """The extended enum carries FL events first class (was gap 1)."""
    log = FLEventLogger(client, registry, num_groups=3, config=config)
    log.log_local_training(2, 7, {"loss": 0.3, "epochs": 3})
    record = client.attestations[-1]

    assert record["action"]["type"] == "local training"
    information = record["action"]["information"]
    assert information["event_type"] == LOCAL_TRAINING
    assert information["hospital_group"] == 2
    assert information["training_round"] == 7


def test_client_round_batches_the_event_pair(client, registry, config):
    """Training + submission for one group travel in a single request."""
    log = FLEventLogger(client, registry, num_groups=3, config=config)
    attestations = log.log_client_round(1, 4, {"loss": 0.2, "epochs": 3}, 433)

    assert len(attestations) == 2
    assert client.batch_calls == 1
    assert [a["action"]["type"] for a in attestations] == [
        "local training",
        "update submission",
    ]
    assert log.event_counts() == {LOCAL_TRAINING: 1, UPDATE_SUBMISSION: 1}
    assert all(
        a["party"]
        == {"name": "hospital-group-1", "data_controller": "joint_controller"}
        for a in attestations
    )


def test_update_submission_states_that_no_raw_data_moved(
    client, registry, config
):
    log = FLEventLogger(client, registry, num_groups=3, config=config)
    log.log_update_submission(1, 3, 433)
    information = client.attestations[-1]["action"]["information"]

    assert information["raw_data_shared"] is False
    assert information["shared_artefact"] == "model_weights"
    assert information["examples_contributed"] == 433
    assert information["recipient"] == "aggregation-server"


def test_events_are_attributed_to_the_acting_party(client, registry, config):
    log = FLEventLogger(client, registry, num_groups=3, config=config)
    log.log_local_training(1, 1, {"loss": 0.4, "epochs": 3})
    log.log_aggregation(1, 3, {"total_examples": 900})

    assert client.attestations[0]["party"]["name"] == "hospital-group-1"
    assert client.attestations[1]["party"]["name"] == "aggregation-server"


# -- Erasure -------------------------------------------------------------


def _handler(client, config):
    manager = ConsentManager(client, config)
    registry = manager.establish_all(["pt-a", "pt-b"])
    logger_ = FLEventLogger(client, registry, num_groups=2, config=config)
    return manager, logger_, ErasureHandler(client, manager, logger_)


def test_erasure_revokes_consent_and_completes_the_request(client, config):
    _, _, handler = _handler(client, config)
    partitions = [FakePartition(0, ["pt-a"]), FakePartition(1, ["pt-b"])]

    outcome = handler.handle_erasure_request("pt-a", partitions)

    assert outcome.consent_revoked is True
    assert outcome.groups_affected == [0]
    assert client.dsrs[outcome.request_id]["status"] == "Completed"
    assert client.dsrs[outcome.request_id]["type"] == DSR_DELETE
    assert handler.verify_erasure("pt-a") is True


def test_erasure_reports_rounds_that_cannot_be_undone(client, config):
    """The honest part: averaged contributions survive erasure."""
    _, event_logger, handler = _handler(client, config)
    for server_round in (1, 2, 3):
        event_logger.log_local_training(0, server_round, {"loss": 0.4, "epochs": 3})

    outcome = handler.handle_erasure_request("pt-a", [FakePartition(0, ["pt-a"])])

    assert outcome.rounds_influenced == [1, 2, 3]
    assert outcome.model_retraining_required is True
    assert "retraining" in outcome.notes


def test_erasure_before_training_needs_no_retraining(client, config):
    _, _, handler = _handler(client, config)
    outcome = handler.handle_erasure_request("pt-a", [FakePartition(0, ["pt-a"])])

    assert outcome.rounds_influenced == []
    assert outcome.model_retraining_required is False


def test_erasure_spans_every_group_holding_the_patient(client, config):
    """A patient in two hospitals is erased from both (Article 26)."""
    _, _, handler = _handler(client, config)
    partitions = [FakePartition(0, ["pt-a"]), FakePartition(1, ["pt-a", "pt-b"])]

    outcome = handler.handle_erasure_request("pt-a", partitions)
    assert outcome.groups_affected == [0, 1]


# -- Live service --------------------------------------------------------


def _service_up() -> bool:
    try:
        return OTraceClient().is_available()
    except Exception:
        return False


@pytest.mark.skipif(not _service_up(), reason="OTrace service not running")
def test_live_service_accepts_the_full_flow():
    """Integration check against the running OTrace service."""
    client = OTraceClient()
    manager = ConsentManager(client)
    registry = manager.establish_all(["live-test-patient"])

    assert manager.verify_data_use("live-test-patient")["valid"] is True

    log = FLEventLogger(client, registry, num_groups=1)
    attestation = log.log_local_training(0, 1, {"loss": 0.5, "epochs": 3})

    assert attestation["id"]
    information = attestation["action"]["information"]
    assert information["event_type"] == LOCAL_TRAINING
    assert information["data_controller_role"] == "joint_controller"
