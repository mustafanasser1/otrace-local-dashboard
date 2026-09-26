"""Tests for differentially private metric release.

OpenDP draws from a secure RNG that is deliberately not seedable, so
these tests are statistical where they must be - with failure
probabilities small enough to ignore - and exact where they can be
(accounting, clipping, validation).
"""

import pytest

from training.dp_metrics import DPMetricsReporter, opendp_version


def test_epsilon_accounting_follows_sequential_composition():
    reporter = DPMetricsReporter(epsilon_per_query=0.5, num_examples=345)
    reporter.privatize({"accuracy": 0.8, "auc": 0.75, "f1": 0.4})

    assert reporter.queries_released == 3
    assert reporter.epsilon_spent == pytest.approx(1.5)


def test_high_epsilon_release_stays_close_to_the_true_value():
    """With a huge budget the mechanism is nearly the identity."""
    reporter = DPMetricsReporter(epsilon_per_query=1e6, num_examples=345)
    released = reporter.release(0.75)
    assert released == pytest.approx(0.75, abs=1e-3)


def test_low_epsilon_release_actually_perturbs():
    """With a tiny budget the noise dominates.

    Statistical: the chance that 20 draws at scale 100 all land within
    0.1 of the true value is ~(0.002)^20 - not a flake risk.
    """
    reporter = DPMetricsReporter(epsilon_per_query=1e-3, num_examples=10)
    diffs = [abs(reporter.release(0.5) - 0.5) for _ in range(20)]
    assert max(diffs) > 0.1


def test_released_values_are_clipped_to_valid_range():
    reporter = DPMetricsReporter(epsilon_per_query=1e-4, num_examples=5)
    for _ in range(50):
        value = reporter.release(0.99)
        assert 0.0 <= value <= 1.0


def test_privatize_releases_every_metric_under_its_own_query():
    reporter = DPMetricsReporter(epsilon_per_query=1e6, num_examples=345)
    raw = {"accuracy": 0.8, "auc": 0.75}
    released = reporter.privatize(raw)

    assert set(released) == set(raw)
    for name in raw:
        assert released[name] == pytest.approx(raw[name], abs=1e-3)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"epsilon_per_query": 0, "num_examples": 100},
        {"epsilon_per_query": -1.0, "num_examples": 100},
        {"epsilon_per_query": 1.0, "num_examples": 0},
    ],
)
def test_invalid_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        DPMetricsReporter(**kwargs)


def test_opendp_version_is_reportable():
    assert opendp_version() not in ("", None)
