"""Secure aggregation by pairwise additive masking.

The scheme is the core of Bonawitz et al. (CCS 2017), reduced to what a
prototype needs. Every ordered pair of clients ``(i, j)`` with ``i < j``
shares a mask derived from a common seed. Client ``i`` adds the mask to
its update, client ``j`` subtracts the same mask, so each submission the
server receives is buried under random noise - but the noise cancels
exactly in the sum, and FedAvg only ever needs the sum.

What the server sees per client is ``n_i * u_i + m_i`` (the
example-weighted update plus that client's net mask). What it can
compute is only ``sum_i(n_i * u_i)``, because ``sum_i(m_i) == 0``.
Dividing by the total example count yields the identical FedAvg result
of the unmasked protocol.

Two honest simplifications, both named rather than hidden:

* **Key agreement is simulated.** In the real protocol each pair
  establishes its seed with a Diffie-Hellman exchange. Here the pairwise
  seeds are derived from a configured base seed, which stands in for
  that exchange; the masking arithmetic - the part this prototype
  evaluates - is unchanged.
* **No dropout recovery.** Bonawitz's secret-sharing machinery for
  clients that disappear mid-round is out of scope; the three hospital
  consortia in this experiment are assumed present for every round.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

#: Standard deviation of the pairwise masks. The updates are weighted
#: by example counts (~500 examples x weights of order 1), so masks
#: need to sit well above ~10^2 to drown a submission; float64
#: accumulation keeps the cancellation error at ~1e-11, orders of
#: magnitude below model precision.
MASK_SCALE = 1e4


def _pair_generator(base_seed: int, server_round: int, i: int, j: int) -> np.random.Generator:
    """Deterministic generator for the pair (i, j) in a given round.

    Both members of the pair derive the same stream, which is what lets
    one add and the other subtract the identical mask. A fresh stream
    per round prevents mask reuse across rounds.
    """
    return np.random.default_rng(
        np.random.SeedSequence(entropy=[base_seed, server_round, i, j])
    )


class PairwiseMasker:
    """One client's share of the masking scheme.

    Args:
        client_id: this client's index in the federation.
        num_clients: total number of participating clients.
        base_seed: stands in for pairwise key agreement (see module
            docstring).
    """

    def __init__(self, client_id: int, num_clients: int, base_seed: int):
        self.client_id = client_id
        self.num_clients = num_clients
        self.base_seed = base_seed

    def _net_mask(
        self, shapes: list[tuple], server_round: int
    ) -> list[np.ndarray]:
        """This client's net mask: add towards higher ids, subtract towards lower."""
        totals = [np.zeros(shape, dtype=np.float64) for shape in shapes]
        for other in range(self.num_clients):
            if other == self.client_id:
                continue
            low, high = sorted((self.client_id, other))
            rng = _pair_generator(self.base_seed, server_round, low, high)
            sign = 1.0 if self.client_id == low else -1.0
            for total, shape in zip(totals, shapes):
                total += sign * rng.normal(0.0, MASK_SCALE, size=shape)
        return totals

    def mask_update(
        self,
        weights: list[np.ndarray],
        num_examples: int,
        server_round: int,
    ) -> list[np.ndarray]:
        """Weight this client's update by its example count and mask it.

        The example weighting happens client-side so that the server's
        only operation is a plain sum - the shape FedAvg needs and the
        only shape under which the masks cancel.
        """
        return [
            num_examples * w.astype(np.float64) + m
            for w, m in zip(weights, self._net_mask([w.shape for w in weights], server_round))
        ]


def secure_aggregate(
    masked_updates: list[list[np.ndarray]],
    example_counts: list[int],
) -> list[np.ndarray]:
    """Sum the masked submissions and divide by the total example count.

    Because every pairwise mask appears once positively and once
    negatively across the submissions, the sum equals
    ``sum_i(n_i * u_i)`` and the division reproduces FedAvg exactly
    (up to floating-point error far below model precision).
    """
    total_examples = sum(example_counts)
    summed = [
        np.sum([update[layer] for update in masked_updates], axis=0)
        for layer in range(len(masked_updates[0]))
    ]
    aggregated = [
        (layer_sum / total_examples).astype(np.float32) for layer_sum in summed
    ]
    logger.debug(
        "secure aggregation over %d clients, %d examples",
        len(masked_updates),
        total_examples,
    )
    return aggregated
