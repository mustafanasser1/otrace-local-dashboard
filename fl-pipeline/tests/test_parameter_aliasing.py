"""Regression test: exchanged weights must not alias the live model.

``Tensor.numpy()`` shares memory with its tensor. Without a copy, an
update already handed to the server would keep changing as the client
trained on, so the server could aggregate weights that no client ever
actually submitted.
"""

import numpy as np
import torch

from models.sepsis_model import SepsisModel, get_parameters
from training.federated_training import HospitalClient
from training.local_training import load_training_config, make_loader, train_epochs

from tests.test_federated_training import make_partition


def test_returned_parameters_do_not_alias_model_weights():
    torch.manual_seed(0)
    model = SepsisModel(input_dim=5)
    snapshot = get_parameters(model)
    frozen = [array.copy() for array in snapshot]

    rng = np.random.default_rng(0)
    x = rng.normal(size=(32, 5))
    y = (x[:, 0] > 0).astype(float)
    train_epochs(model, make_loader(x, y, 8, shuffle=False), 3, 0.01)

    for before, after in zip(frozen, snapshot, strict=True):
        np.testing.assert_array_equal(before, after)


def test_submitted_update_is_stable_across_later_rounds():
    """A client's round-1 update must not change when round 2 runs."""
    client = HospitalClient(make_partition(0), load_training_config())
    round_one, _, _ = client.fit(client.get_parameters())
    captured = [array.copy() for array in round_one]

    client.fit(client.get_parameters())

    for submitted, still in zip(captured, round_one, strict=True):
        np.testing.assert_array_equal(submitted, still)
