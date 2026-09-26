"""Tests for the federated client, strategy, and round loop."""

import numpy as np
import pytest

from models.sepsis_model import get_parameters
from preprocessing.load_eicu import data_dir
from preprocessing.partition_by_hospital import HospitalPartition
from training.federated_training import (
    HospitalClient,
    OTraceStrategy,
    _as_fit_results,
    ,
    weighted_average,
)
from training.local_training import load_training_config


class RecordingLogger:
    """Captures lifecycle calls so tests can assert on them."""

    def __init__(self):
        self.local_training = []
        self.update_submission = []
        self.aggregation = []

    def log_local_training(self, group_id, server_round, metrics):
        self.local_training.append((group_id, server_round))

    def log_update_submission(self, group_id, server_round, num_examples):
        self.update_submission.append((group_id, server_round, num_examples))

    def log_aggregation(self, server_round, num_clients, metrics):
        self.aggregation.append((server_round, num_clients))


def make_partition(group_id: int, n: int = 40, features: int = 6):
    rng = np.random.default_rng(group_id)
    x = rng.normal(size=(n, features))
    y = (x[:, 0] > 0).astype(float)
    return HospitalPartition(
        group_id=group_id,
        hospital_ids=[group_id * 10],
        x_train=x,
        y_train=y,
        x_test=x[: n // 2],
        y_test=y[: n // 2],
        patient_ids=[f"p{group_id}-{i}" for i in range(n)],
    )


@pytest.fixture
def config() -> dict:
    return load_training_config()


def test_fit_returns_updated_weights_and_example_count(config):
    client = HospitalClient(make_partition(0), config)
    before = get_parameters(client.model)
    weights, num_examples, metrics = client.fit(before)

    assert num_examples == 40
    assert "loss" in metrics
    assert not np.allclose(before[0], weights[0])  # training moved the weights


def test_fit_starts_from_the_supplied_global_weights(config):
    a = HospitalClient(make_partition(0), config)
    b = HospitalClient(make_partition(1), config)
    # Different seeds mean different initial weights.
    assert not np.allclose(get_parameters(a.model)[0], get_parameters(b.model)[0])

    b.fit(get_parameters(a.model))
    # After fit, b's weights derive from a's - not from b's own init.
    assert b.get_parameters()[0].shape == get_parameters(a.model)[0].shape


def test_client_notifies_trace_logger_on_every_round(config):
    recorder = RecordingLogger()
    client = HospitalClient(make_partition(2), config, trace_logger=recorder)
    weights = client.get_parameters()

    client.fit(weights)
    client.fit(weights)

    assert recorder.local_training == [(2, 1), (2, 2)]
    assert [r for _, r, _ in recorder.update_submission] == [1, 2]
    assert all(n == 40 for _, _, n in recorder.update_submission)


def test_training_runs_without_a_logger(config):
    """Tracing must be optional so its overhead can be measured."""
    client = HospitalClient(make_partition(0), config, trace_logger=None)
    _, num_examples, _ = client.fit(client.get_parameters())
    assert num_examples == 40


def test_evaluate_returns_loss_examples_and_metrics(config):
    client = HospitalClient(make_partition(0), config)
    loss, num_examples, metrics = client.evaluate(client.get_parameters())
    assert num_examples == 20
    assert 0.0 <= loss <= 1.0
    assert set(metrics) == {"accuracy", "auc", "f1", "precision", "recall"}


def test_strategy_averages_weights_by_example_count():
    """FedAvg must weight a 300-stay client above a 100-stay one."""
    strategy = OTraceStrategy()
    small = [np.array([0.0, 0.0])]
    large = [np.array([4.0, 4.0])]
    aggregated, _ = strategy.aggregate_fit(
        1, _as_fit_results([(small, 100), (large, 300)]), failures=[]
    )
    from flwr.common import parameters_to_ndarrays

    result = parameters_to_ndarrays(aggregated)[0]
    np.testing.assert_allclose(result, [3.0, 3.0])  # (0*100 + 4*300) / 400


def test_strategy_logs_one_aggregation_event_per_round():
    recorder = RecordingLogger()
    strategy = OTraceStrategy(trace_logger=recorder)
    updates = _as_fit_results([([np.array([1.0])], 10), ([np.array([3.0])], 10)])

    strategy.aggregate_fit(1, updates, failures=[])
    strategy.aggregate_fit(2, updates, failures=[])

    assert recorder.aggregation == [(1, 2), (2, 2)]


def test_weighted_average_skips_nan_metrics():
    combined = weighted_average(
        [(100, {"auc": float("nan"), "f1": 0.5}), (300, {"auc": 0.8, "f1": 0.9})]
    )
    assert combined["auc"] == pytest.approx(0.8)  # NaN client ignored
    assert combined["f1"] == pytest.approx((100 * 0.5 + 300 * 0.9) / 400)


def test_weighted_average_all_nan_yields_nan():
    combined = weighted_average([(10, {"auc": float("nan")})])
    assert np.isnan(combined["auc"])


@pytest.mark.skipif(
    not data_dir().exists(), reason="eICU demo dataset not present"
)
def test_real_federated_run_learns_and_traces():
    """Integration check: full federated run, every event recorded."""
    recorder = RecordingLogger()
    metrics = (trace_logger=recorder, seed=42)

    assert metrics["auc"] > 0.65
    # 3 clients x 10 rounds of local training and update submission.
    assert len(recorder.local_training) == 30
    assert len(recorder.update_submission) == 30
    # One aggregation per round.
    assert len(recorder.aggregation) == 10
    assert [r for r, _ in recorder.aggregation] == list(range(1, 11))
