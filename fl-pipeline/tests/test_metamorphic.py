"""Metamorphic test suite - Specific Objective 6 of the research plan.

Where a conventional test needs a known expected output, a metamorphic
test needs only a *relation*: transform the input in a controlled way
and state how the output must (or must not) change. That fits this
system well, because "the correct aggregated model" has no oracle, but
"reordering hospitals must not change it" is checkable exactly.

Each test names its relation explicitly:

  MR1  client permutation invariance   (aggregation)
  MR2  mask-seed invariance            (secure aggregation)
  MR3  example-weight scale invariance (aggregation)
  MR4  duplicate-client equivalence    (aggregation)
  MR5  round-count proportionality     (trace)
  MR6  consent-withdrawal monotonicity (consent state machine)
"""

import numpy as np
import pytest

from training.secure_aggregation import PairwiseMasker, secure_aggregate

NUM_CLIENTS = 3


def _updates(seed: int = 7) -> tuple[list[list[np.ndarray]], list[int]]:
    rng = np.random.default_rng(seed)
    shapes = [(6, 3), (3,), (3, 1)]
    updates = [
        [rng.normal(0, 0.5, size=s).astype(np.float32) for s in shapes]
        for _ in range(NUM_CLIENTS)
    ]
    return updates, [422, 433, 427]


def _fedavg(updates, counts):
    total = sum(counts)
    return [
        sum(n * u[layer].astype(np.float64) for n, u in zip(counts, updates)) / total
        for layer in range(len(updates[0]))
    ]


def _masked_aggregate(updates, counts, base_seed, permutation=None):
    order = permutation if permutation is not None else range(len(updates))
    maskers = [PairwiseMasker(i, len(updates), base_seed) for i in range(len(updates))]
    masked = [
        maskers[i].mask_update(updates[i], counts[i], server_round=1) for i in order
    ]
    return secure_aggregate(masked, [counts[i] for i in order])


# -- MR1: client permutation invariance ------------------------------------


def test_mr1_reordering_clients_does_not_change_the_aggregate():
    """Source: aggregate in order 0,1,2. Follow-up: order 2,0,1.

    Relation: outputs identical. FedAvg is a weighted sum; the
    federation must not care which hospital reports first.
    """
    updates, counts = _updates()
    source = _masked_aggregate(updates, counts, base_seed=11)
    follow_up = _masked_aggregate(updates, counts, base_seed=11, permutation=[2, 0, 1])

    for a, b in zip(source, follow_up):
        np.testing.assert_allclose(a, b, atol=1e-6)


# -- MR2: mask-seed invariance ----------------------------------------------


def test_mr2_changing_mask_seeds_changes_submissions_not_the_aggregate():
    """Source: masks from seed A. Follow-up: masks from seed B.

    Relation: individual masked submissions differ (the server sees
    different noise) while the aggregate is unchanged - the masks are
    provably irrelevant to the result they protect.
    """
    updates, counts = _updates()

    masker_a = PairwiseMasker(0, NUM_CLIENTS, 11)
    masker_b = PairwiseMasker(0, NUM_CLIENTS, 12)
    submission_a = masker_a.mask_update(updates[0], counts[0], server_round=1)
    submission_b = masker_b.mask_update(updates[0], counts[0], server_round=1)
    assert any(not np.allclose(a, b) for a, b in zip(submission_a, submission_b))

    aggregate_a = _masked_aggregate(updates, counts, base_seed=11)
    aggregate_b = _masked_aggregate(updates, counts, base_seed=12)
    for a, b in zip(aggregate_a, aggregate_b):
        np.testing.assert_allclose(a, b, atol=1e-6)


# -- MR3: example-weight scale invariance ------------------------------------


def test_mr3_scaling_every_example_count_leaves_the_average_unchanged():
    """Source: counts n_i. Follow-up: counts 10 * n_i.

    Relation: identical output. FedAvg weights are relative; a uniform
    rescaling (e.g. counting samples in different units) must cancel.
    """
    updates, counts = _updates()
    source = _fedavg(updates, counts)
    follow_up = _fedavg(updates, [10 * n for n in counts])

    for a, b in zip(source, follow_up):
        np.testing.assert_allclose(a, b, atol=1e-9)


# -- MR4: duplicate-client equivalence ----------------------------------------


def test_mr4_splitting_a_client_in_two_halves_is_equivalent():
    """Source: client 0 with n examples. Follow-up: two copies of
    client 0 with n/2 each.

    Relation: identical output. A consortium reporting as one party or
    as two equal halves must produce the same global model - the
    federation aggregates data quantities, not party counts.
    """
    updates, counts = _updates()
    split_updates = [updates[0], updates[0]] + updates[1:]
    split_counts = [counts[0] / 2, counts[0] / 2] + counts[1:]

    source = _fedavg(updates, counts)
    follow_up = _fedavg(split_updates, split_counts)

    for a, b in zip(source, follow_up):
        np.testing.assert_allclose(a, b, atol=1e-9)


# -- MR5: round-count proportionality -----------------------------------------


class _CountingLogger:
    """Records event counts without any backing service."""

    def __init__(self):
        self.counts = {"local": 0, "submit": 0, "aggregate": 0}

    def log_local_training(self, group_id, server_round, metrics):
        self.counts["local"] += 1

    def log_update_submission(self, group_id, server_round, num_examples):
        self.counts["submit"] += 1

    def log_client_round(self, group_id, server_round, metrics, num_examples):
        self.counts["local"] += 1
        self.counts["submit"] += 1

    def log_aggregation(self, server_round, num_clients, metrics):
        self.counts["aggregate"] += 1


def _run_with_rounds(monkeypatch, rounds: int) -> dict:
    import training.federated_training as ft

    config = ft.load_training_config()
    config["fl"]["num_rounds"] = rounds
    monkeypatch.setattr(ft, "load_training_config", lambda: config)

    logger = _CountingLogger()
    ft.run_federated_training(trace_logger=logger, seed=1)
    return logger.counts


def test_mr5_doubling_rounds_doubles_every_trace_count(monkeypatch):
    """Source: R rounds. Follow-up: 2R rounds.

    Relation: every event count exactly doubles. The trace must scale
    with the process it records; a count that does not is evidence of
    dropped or duplicated attestations.
    """
    two = _run_with_rounds(monkeypatch, 2)
    four = _run_with_rounds(monkeypatch, 4)

    assert two["aggregate"] == 2 and four["aggregate"] == 4
    for key in two:
        assert four[key] == 2 * two[key], key


# -- MR6: consent-withdrawal monotonicity -------------------------------------


def test_mr6_withdrawal_flips_the_verdict_and_nothing_restores_it():
    """Source: a data-use check under accepted consent (valid). Follow-up:
    the same check after revocation.

    Relation: valid -> invalid, and repeating the identical check any
    number of times never returns valid. Consent withdrawal under
    Article 7(3) is monotonic: no operation short of a new consent
    grant may resurrect the legal basis.
    """
    from tests.test_otrace_integration import FakeOTraceClient
    from otrace_integration.consent_manager import ConsentManager
    from otrace_integration.otrace_client import load_otrace_config

    manager = ConsentManager(FakeOTraceClient(), load_otrace_config())
    manager.establish_all(["pt-mr6"])

    assert manager.verify_data_use("pt-mr6")["valid"] is True
    manager.revoke("pt-mr6")
    for _ in range(3):
        assert manager.verify_data_use("pt-mr6")["valid"] is False
