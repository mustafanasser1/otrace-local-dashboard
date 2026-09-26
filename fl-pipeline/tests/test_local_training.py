"""Tests for metrics and the centralised training loop."""

import numpy as np
import pytest
import torch

from models.sepsis_model import SepsisModel, get_parameters
from preprocessing.load_eicu import data_dir
from training.local_training import (
    evaluate,
    load_training_config,
    make_loader,
    pooled_dataset,
    run_local_training,
    train_epochs,
)
from training.metrics import compute_metrics


class _FakePartition:
    def __init__(self, n: int, features: int, value: float):
        self.x_train = np.full((n, features), value)
        self.y_train = np.zeros(n)
        self.x_test = np.full((n // 2, features), value)
        self.y_test = np.ones(n // 2)


def test_compute_metrics_scores_perfect_predictions():
    y_true = np.array([0, 0, 1, 1])
    metrics = compute_metrics(y_true, np.array([0.1, 0.2, 0.8, 0.9]))
    assert metrics["accuracy"] == 1.0
    assert metrics["auc"] == 1.0
    assert metrics["f1"] == 1.0


def test_compute_metrics_returns_nan_auc_for_single_class():
    metrics = compute_metrics(np.array([1, 1, 1]), np.array([0.4, 0.6, 0.8]))
    assert np.isnan(metrics["auc"])
    assert not np.isnan(metrics["accuracy"])


def test_compute_metrics_respects_threshold():
    y_true = np.array([0, 1])
    probs = np.array([0.4, 0.6])
    assert compute_metrics(y_true, probs, threshold=0.5)["accuracy"] == 1.0
    assert compute_metrics(y_true, probs, threshold=0.7)["accuracy"] == 0.5


def test_pooled_dataset_concatenates_every_partition():
    parts = [_FakePartition(10, 4, v) for v in (1.0, 2.0, 3.0)]
    x_train, y_train, x_test, y_test = pooled_dataset(parts)
    assert x_train.shape == (30, 4)
    assert y_train.shape == (30,)
    assert x_test.shape == (15, 4)
    assert y_test.shape == (15,)
    assert set(np.unique(x_train)) == {1.0, 2.0, 3.0}


def test_train_epochs_changes_weights_and_reduces_loss():
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    # Separable problem: label follows the sign of the first feature.
    x = rng.normal(size=(64, 5))
    y = (x[:, 0] > 0).astype(float)

    model = SepsisModel(input_dim=5)
    before = get_parameters(model)[0].copy()
    loader = make_loader(x, y, batch_size=16, shuffle=True)

    first = train_epochs(model, loader, epochs=1, learning_rate=0.01)
    last = train_epochs(model, loader, epochs=20, learning_rate=0.01)

    assert not np.allclose(before, get_parameters(model)[0])
    assert last < first
    assert evaluate(model, x, y)["accuracy"] > 0.8


def test_training_config_has_required_sections():
    config = load_training_config()
    assert config["fl"]["num_clients"] == 3
    assert config["model"]["hidden_layers"] == [64, 32]
    assert config["local_training"]["epochs_per_round"] > 0


@pytest.mark.skipif(
    not data_dir().exists(), reason="eICU demo dataset not present"
)
def test_real_baseline_beats_chance():
    """Integration check: the centralised baseline must actually learn."""
    metrics = run_local_training(seed=42)
    assert metrics["auc"] > 0.65  # chance is 0.5
    assert metrics["recall"] > 0.2  # must find some sepsis cases
