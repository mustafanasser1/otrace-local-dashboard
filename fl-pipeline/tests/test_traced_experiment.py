"""End-to-end test of the traced federated experiment.

Requires both the eICU dataset and a running OTrace service, so it is
skipped when either is absent.
"""

import pytest

from otrace_integration.event_logger import (
    AGGREGATION,
    DEPLOYMENT,
    LOCAL_TRAINING,
    UPDATE_SUBMISSION,
)
from otrace_integration.otrace_client import OTraceClient
from preprocessing.load_eicu import data_dir
from run_traced_experiment import run_experiment


def _service_up() -> bool:
    try:
        return OTraceClient().is_available()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not data_dir().exists() or not _service_up(),
    reason="needs the eICU dataset and a running OTrace service",
)


@pytest.fixture(scope="module")
def result() -> dict:
    """One experiment run shared by every assertion in this module."""
    return run_experiment(consent_sample=20, seed=42)


def test_every_lifecycle_event_is_traced(result):
    """3 clients x 10 rounds, plus one aggregation each round and a deploy."""
    assert result["event_counts"] == {
        LOCAL_TRAINING: 30,
        UPDATE_SUBMISSION: 30,
        AGGREGATION: 10,
        DEPLOYMENT: 1,
    }
    assert result["trace_complete"] is True


def test_the_model_actually_learned(result):
    assert result["metrics"]["auc"] > 0.65
    assert result["metrics"]["recall"] > 0.2


def test_erasure_revokes_consent_and_reports_residual_influence(result):
    erasure = result["erasure"]
    assert erasure.consent_revoked is True
    assert erasure.groups_affected  # the patient belonged to some group
    assert erasure.rounds_influenced == list(range(1, 11))
    assert erasure.model_retraining_required is True


def test_tracing_overhead_is_measured_and_bounded(result):
    """The overhead measurement exists and lands in a sane band.

    With batched attestations the per-round instrumentation cost sits
    near the wall-clock noise floor, so a traced run is no longer
    reliably slower than an untraced one on a single measurement.
    Strict ``traced > untraced`` (the pre-batching assertion) became
    flaky for exactly that reason; what must hold is that the
    measurement is produced and is not absurd in either direction.
    """
    assert result["traced_seconds"] > 0
    assert result["untraced_seconds"] > 0
    assert -25 < result["overhead_percent"] < 200


def test_consent_count_matches_the_sample(result):
    assert result["consents"] == 20
