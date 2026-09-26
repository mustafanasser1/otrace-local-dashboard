"""Differentially private reporting of evaluation metrics.

The registered research plan applies differential privacy to *metrics
and queries*, not to the training loop itself: whatever numbers leave
the system - reported model quality, answers to evaluation queries -
carry calibrated noise, so no released figure depends too strongly on
any one patient's presence in the test data.

The mechanism is Laplace via OpenDP (the OpenDP Project's reference
implementation). Each released metric counts as one query against the
test set; sequential composition applies, so total spend is
``epsilon_per_query x queries_released``, tracked by the reporter and
reported alongside the values.

One named simplification: sensitivity is taken as ``1/n`` for every
released ratio metric. That is exact for accuracy and standard for
error-rate style metrics; AUC's true sensitivity is data-dependent
(order ``1/min(n_pos, n_neg)``), so its noise here is optimistic. A
thesis-grade release would compute per-metric sensitivities - recorded
as future work rather than glossed over.
"""

import logging
from importlib import metadata

import opendp.prelude as dp

logger = logging.getLogger(__name__)

dp.enable_features("contrib")


def opendp_version() -> str:
    """Installed OpenDP version, for the experiment report."""
    try:
        return metadata.version("opendp")
    except metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


class DPMetricsReporter:
    """Releases metrics through the Laplace mechanism and counts the cost.

    Args:
        epsilon_per_query: privacy budget spent per released metric.
        num_examples: size of the test set the metrics are computed on;
            sets the ``1/n`` sensitivity.
        clip_range: released values are clamped to this range - ratio
            metrics live in [0, 1] and noise must not release
            impossible values.
    """

    def __init__(
        self,
        epsilon_per_query: float,
        num_examples: int,
        clip_range: tuple[float, float] = (0.0, 1.0),
    ):
        if epsilon_per_query <= 0:
            raise ValueError("epsilon_per_query must be positive")
        if num_examples <= 0:
            raise ValueError("num_examples must be positive")
        self.epsilon_per_query = float(epsilon_per_query)
        self.sensitivity = 1.0 / num_examples
        self.clip_range = clip_range
        self.queries_released = 0

        scale = self.sensitivity / self.epsilon_per_query
        self._mechanism = dp.m.make_laplace(
            dp.atom_domain(T=float, nan=False),
            dp.absolute_distance(T=float),
            scale=scale,
        )

    @property
    def epsilon_spent(self) -> float:
        """Total budget consumed so far (sequential composition)."""
        return self.queries_released * self.epsilon_per_query

    def release(self, value: float) -> float:
        """One noisy answer to one metric query."""
        self.queries_released += 1
        low, high = self.clip_range
        return float(min(max(self._mechanism(float(value)), low), high))

    def privatize(self, metrics: dict[str, float]) -> dict[str, float]:
        """Release every metric in the mapping under the Laplace mechanism."""
        released = {name: self.release(value) for name, value in metrics.items()}
        logger.info(
            "DP release: %d metrics, epsilon per query %.2f, total spent %.2f "
            "(sensitivity 1/%d)",
            len(released),
            self.epsilon_per_query,
            self.epsilon_spent,
            round(1 / self.sensitivity),
        )
        return released
