"""Tests for pairwise-masking secure aggregation.

The two properties that matter: an individual masked submission tells
the server nothing (the mask dominates it), and the aggregate equals
plain FedAvg exactly enough that turning masking on costs no utility.
"""

import numpy as np
import pytest

from training.secure_aggregation import (
    MASK_SCALE,
    PairwiseMasker,
    secure_aggregate,
)

BASE_SEED = 99
NUM_CLIENTS = 3


def _fake_updates(seed: int = 0) -> tuple[list[list[np.ndarray]], list[int]]:
    """Three clients' worth of plausible model weights."""
    rng = np.random.default_rng(seed)
    shapes = [(8, 4), (4,), (4, 1)]
    updates = [
        [rng.normal(0, 0.5, size=s).astype(np.float32) for s in shapes]
        for _ in range(NUM_CLIENTS)
    ]
    counts = [422, 433, 427]
    return updates, counts


def _fedavg(updates, counts):
    total = sum(counts)
    return [
        sum(n * u[layer].astype(np.float64) for n, u in zip(counts, updates)) / total
        for layer in range(len(updates[0]))
    ]


def test_masks_cancel_and_reproduce_fedavg():
    """The aggregate of masked updates equals the plain weighted average."""
    updates, counts = _fake_updates()
    maskers = [PairwiseMasker(i, NUM_CLIENTS, BASE_SEED) for i in range(NUM_CLIENTS)]

    masked = [
        m.mask_update(u, n, server_round=1)
        for m, (u, n) in zip(maskers, zip(updates, counts))
    ]
    aggregated = secure_aggregate(masked, counts)
    expected = _fedavg(updates, counts)

    for got, want in zip(aggregated, expected):
        np.testing.assert_allclose(got, want, atol=1e-4)


def test_single_submission_is_dominated_by_its_mask():
    """One masked update on its own reveals nothing about the weights."""
    updates, counts = _fake_updates()
    masker = PairwiseMasker(0, NUM_CLIENTS, BASE_SEED)
    masked = masker.mask_update(updates[0], counts[0], server_round=1)

    for masked_layer, raw_layer in zip(masked, updates[0]):
        weighted = counts[0] * raw_layer.astype(np.float64)
        residual = masked_layer - weighted
        # The mask actually present is on the order of MASK_SCALE, far
        # above the weighted update itself.
        assert np.abs(residual).mean() > 10 * np.abs(weighted).mean()
        # And the masked values do not correlate usefully with the raw
        # ones. Sample correlation over a handful of points is pure
        # noise, so only layers with enough elements are checked.
        flat_masked = masked_layer.ravel()
        flat_true = weighted.ravel()
        if flat_true.size >= 30 and flat_true.std() > 0:
            corr = np.corrcoef(flat_masked, flat_true)[0, 1]
            assert abs(corr) < 0.5


def test_net_masks_sum_to_zero_across_clients():
    updates, counts = _fake_updates()
    maskers = [PairwiseMasker(i, NUM_CLIENTS, BASE_SEED) for i in range(NUM_CLIENTS)]

    shapes = [u.shape for u in updates[0]]
    net = [np.zeros(s, dtype=np.float64) for s in shapes]
    for masker in maskers:
        for total, share in zip(net, masker._net_mask(shapes, server_round=3)):
            total += share

    for layer in net:
        np.testing.assert_allclose(layer, 0.0, atol=1e-6 * MASK_SCALE)


def test_masks_differ_between_rounds():
    """Mask reuse across rounds would leak update deltas; there is none."""
    updates, counts = _fake_updates()
    masker = PairwiseMasker(0, NUM_CLIENTS, BASE_SEED)

    round_1 = masker.mask_update(updates[0], counts[0], server_round=1)
    round_2 = masker.mask_update(updates[0], counts[0], server_round=2)

    assert any(
        not np.allclose(a, b) for a, b in zip(round_1, round_2)
    )


def test_two_clients_is_the_minimum_working_federation():
    updates, counts = _fake_updates()
    updates, counts = updates[:2], counts[:2]
    maskers = [PairwiseMasker(i, 2, BASE_SEED) for i in range(2)]

    masked = [
        m.mask_update(u, n, server_round=1)
        for m, (u, n) in zip(maskers, zip(updates, counts))
    ]
    aggregated = secure_aggregate(masked, counts)

    for got, want in zip(aggregated, _fedavg(updates, counts)):
        np.testing.assert_allclose(got, want, atol=1e-4)
