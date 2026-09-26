"""Tests for the model definition and its parameter exchange format."""

import numpy as np
import pytest
import torch

from models.sepsis_model import (
    SepsisModel,
    count_parameters,
    get_parameters,
    set_parameters,
)


@pytest.fixture
def model() -> SepsisModel:
    torch.manual_seed(0)
    return SepsisModel(input_dim=10)


def test_forward_returns_probability_per_row(model):
    out = model(torch.randn(5, 10))
    assert out.shape == (5, 1)
    assert ((out >= 0) & (out <= 1)).all()


def test_get_parameters_round_trips_through_set_parameters(model):
    original = get_parameters(model)
    fresh = SepsisModel(input_dim=10)
    # A freshly initialised model starts with different weights.
    assert not np.allclose(original[0], get_parameters(fresh)[0])

    set_parameters(fresh, original)
    for before, after in zip(original, get_parameters(fresh), strict=True):
        np.testing.assert_allclose(before, after)


def test_set_parameters_rejects_mismatched_shapes(model):
    with pytest.raises((RuntimeError, ValueError)):
        set_parameters(model, get_parameters(SepsisModel(input_dim=99)))


def test_identical_weights_give_identical_predictions(model):
    twin = SepsisModel(input_dim=10)
    set_parameters(twin, get_parameters(model))
    model.eval()
    twin.eval()
    x = torch.randn(4, 10)
    with torch.no_grad():
        torch.testing.assert_close(model(x), twin(x))


def test_count_parameters_matches_architecture():
    # 10->64 (704) + 64->32 (2080) + 32->1 (33)
    assert count_parameters(SepsisModel(input_dim=10)) == 704 + 2080 + 33
