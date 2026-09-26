"""Federated sepsis training across hospital groups.

Step two of the supervisor's prototype sequence: the same model as the
local baseline, trained without any hospital sharing raw records. Each
hospital group keeps its own data, trains locally, and sends only model
updates to the server, which averages them with FedAvg.

Both the client and the aggregation strategy are real Flower components
(:class:`flwr.client.NumPyClient` and :class:`flwr.server.strategy.FedAvg`).
They are driven by an in-process round loop rather than Flower's Ray
simulation: the federated semantics are identical, while the run stays
deterministic and every instrumentation point remains directly
observable - which matters because OTrace attestations get attached to
these exact call sites in the next step.

Run directly to train and report metrics::

    python -m training.federated_training
"""

import logging
from typing import Protocol

import flwr as fl
import numpy as np
import torch
from flwr.common import (
    Code,
    FitRes,
    Status,
    ndarrays_to_parameters,
    parameters_to_ndarrays,
)

from models.sepsis_model import SepsisModel, get_parameters, set_parameters
from preprocessing.partition_by_hospital import HospitalPartition, build_partitions
from training.local_training import (
    evaluate,
    load_training_config,
    make_loader,
    train_epochs,
)
from training.dp_metrics import DPMetricsReporter
from training.metrics import compute_metrics, format_metrics
from training.secure_aggregation import PairwiseMasker, secure_aggregate

logger = logging.getLogger(__name__)


class TraceLogger(Protocol):
    """Hook for recording training lifecycle events.

    The OTrace integration layer implements this. Training runs with no
    logger at all, which keeps this module free of any compliance
    concern and lets the overhead of tracing be measured by comparing a
    traced run against an untraced one.
    """

    def log_local_training(
        self, group_id: int, server_round: int, metrics: dict
    ) -> None: ...

    def log_update_submission(
        self, group_id: int, server_round: int, num_examples: int
    ) -> None: ...

    def log_aggregation(
        self, server_round: int, num_clients: int, metrics: dict
    ) -> None: ...


class HospitalClient(fl.client.NumPyClient):
    """One hospital group participating in federated training.

    Args:
        partition: this group's data and identity.
        config: parsed training configuration.
        trace_logger: optional lifecycle event recorder.
    """

    def __init__(
        self,
        partition: HospitalPartition,
        config: dict,
        trace_logger: TraceLogger | None = None,
    ):
        self.partition = partition
        self.config = config
        self.trace_logger = trace_logger
        self.model = SepsisModel(
            input_dim=partition.num_features,
            hidden_layers=tuple(config["model"]["hidden_layers"]),
        )
        # Counteract this group's own class imbalance.
        positives = max((partition.y_train == 1).sum(), 1)
        self.pos_weight = float((partition.y_train == 0).sum() / positives)
        self.server_round = 0

    @property
    def group_id(self) -> int:
        return self.partition.group_id

    def get_parameters(self, config: dict | None = None) -> list[np.ndarray]:
        """Current local weights."""
        return get_parameters(self.model)

    def fit(
        self, parameters: list[np.ndarray], config: dict | None = None
    ) -> tuple[list[np.ndarray], int, dict]:
        """Train on local data starting from the global weights.

        Raw records never leave this method - only the returned weights
        do. That boundary is what the trace layer attests to.
        """
        self.server_round += 1
        set_parameters(self.model, parameters)

        local = self.config["local_training"]
        loader = make_loader(
            self.partition.x_train,
            self.partition.y_train,
            local["batch_size"],
            shuffle=True,
        )
        loss = train_epochs(
            self.model,
            loader,
            local["epochs_per_round"],
            local["learning_rate"],
            self.pos_weight,
        )
        num_examples = len(self.partition.x_train)
        metrics = {"loss": loss, "epochs": local["epochs_per_round"]}

        if self.trace_logger is not None:
            # The two events happen back to back for the same party, so a
            # logger that can post them as one batch is offered the pair.
            if hasattr(self.trace_logger, "log_client_round"):
                self.trace_logger.log_client_round(
                    self.group_id, self.server_round, metrics, num_examples
                )
            else:
                self.trace_logger.log_local_training(
                    self.group_id, self.server_round, metrics
                )
                self.trace_logger.log_update_submission(
                    self.group_id, self.server_round, num_examples
                )

        logger.debug(
            "client %d round %d: trained on %d stays, loss=%.4f",
            self.group_id,
            self.server_round,
            num_examples,
            loss,
        )
        return self.get_parameters(), num_examples, metrics

    def evaluate(
        self, parameters: list[np.ndarray], config: dict | None = None
    ) -> tuple[float, int, dict]:
        """Score the global model against this group's held-out data."""
        set_parameters(self.model, parameters)
        metrics = evaluate(self.model, self.partition.x_test, self.partition.y_test)
        return 1.0 - metrics["accuracy"], len(self.partition.x_test), metrics


def _aggregate_fit_metrics(
    per_client: list[tuple[int, dict]],
) -> dict[str, float]:
    """Example-weighted mean of the clients' training loss.

    Clients that report no loss (the typed wrappers used for
    aggregation carry weights only) are simply skipped.
    """
    reported = [(n, m["loss"]) for n, m in per_client if "loss" in m]
    total = sum(n for n, _ in reported)
    if not total:
        return {}
    return {"loss": sum(n * loss for n, loss in reported) / total}


class OTraceStrategy(fl.server.strategy.FedAvg):
    """FedAvg that records an attestation for every aggregation.

    Aggregation is the point where separately-held updates are combined,
    so it is the event the accountability story turns on.
    """

    def __init__(self, trace_logger: TraceLogger | None = None, **kwargs):
        kwargs.setdefault("fit_metrics_aggregation_fn", _aggregate_fit_metrics)
        super().__init__(**kwargs)
        self.trace_logger = trace_logger

    def aggregate_fit(self, server_round: int, results: list, failures: list):
        aggregated, metrics = super().aggregate_fit(server_round, results, failures)

        if self.trace_logger is not None:
            self.trace_logger.log_aggregation(
                server_round,
                len(results),
                {"total_examples": sum(r.num_examples for _, r in results)},
            )
        return aggregated, metrics


def _as_fit_results(client_updates: list[tuple[list[np.ndarray], int]]) -> list:
    """Wrap raw client returns in the typed results FedAvg expects."""
    return [
        (
            None,  # ClientProxy: unused by FedAvg's weighted average
            FitRes(
                status=Status(code=Code.OK, message="OK"),
                parameters=ndarrays_to_parameters(weights),
                num_examples=num_examples,
                metrics={},
            ),
        )
        for weights, num_examples in client_updates
    ]


def weighted_average(
    per_client: list[tuple[int, dict[str, float]]],
) -> dict[str, float]:
    """Combine client metrics, weighting each by its example count.

    NaN values are skipped rather than poisoning the average - a small
    client's test split can be single-class, which makes AUC undefined.
    """
    combined: dict[str, float] = {}
    for name in per_client[0][1]:
        pairs = [
            (n, m[name]) for n, m in per_client if not np.isnan(m[name])
        ]
        total = sum(n for n, _ in pairs)
        combined[name] = (
            float(sum(n * v for n, v in pairs) / total) if total else float("nan")
        )
    return combined


def run_federated_training(
    trace_logger: TraceLogger | None = None, seed: int = 42
) -> dict[str, float]:
    """Run the full federated experiment.

    Args:
        trace_logger: optional recorder for lifecycle events. When None,
            training runs with no compliance instrumentation at all.
        seed: torch seed, for reproducible weight initialisation.

    Returns:
        Test metrics of the final global model, pooled across clients.
    """
    torch.manual_seed(seed)
    config = load_training_config()
    rounds = config["fl"]["num_rounds"]

    partitions = build_partitions()
    clients = [HospitalClient(p, config, trace_logger) for p in partitions]
    strategy = OTraceStrategy(trace_logger=trace_logger)

    secure_cfg = config.get("secure_aggregation", {})
    use_secure = bool(secure_cfg.get("enabled", False))
    maskers = (
        [
            PairwiseMasker(i, len(clients), secure_cfg["base_seed"])
            for i in range(len(clients))
        ]
        if use_secure
        else []
    )
    logger.info(
        "Federated training: %d clients, %d rounds, %d local epochs per round, "
        "secure aggregation %s",
        len(clients),
        rounds,
        config["local_training"]["epochs_per_round"],
        "on" if use_secure else "off",
    )

    # Round 0: every client starts from the same global weights.
    global_weights = clients[0].get_parameters()

    for server_round in range(1, rounds + 1):
        updates = [client.fit(global_weights)[:2] for client in clients]

        if use_secure:
            # Each client masks its weighted update before it leaves the
            # client boundary; the server can only recover the sum.
            masked = [
                masker.mask_update(weights, num_examples, server_round)
                for masker, (weights, num_examples) in zip(maskers, updates)
            ]
            example_counts = [num_examples for _, num_examples in updates]
            global_weights = secure_aggregate(masked, example_counts)
            if trace_logger is not None:
                trace_logger.log_aggregation(
                    server_round,
                    len(clients),
                    {
                        "total_examples": sum(example_counts),
                        "aggregation_method": "FedAvg + pairwise masking",
                    },
                )
        else:
            aggregated, _ = strategy.aggregate_fit(
                server_round, _as_fit_results(updates), failures=[]
            )
            global_weights = parameters_to_ndarrays(aggregated)

        scored = [
            (n, m) for _, n, m in (c.evaluate(global_weights) for c in clients)
        ]
        round_metrics = weighted_average(scored)
        logger.info(
            "round %2d/%d  %s", server_round, rounds, format_metrics(round_metrics)
        )

    final = _evaluate_globally(global_weights, partitions, config)
    logger.info("Federated test metrics: %s", format_metrics(final))

    dp_cfg = config.get("differential_privacy", {})
    if dp_cfg.get("enabled", False):
        # Only the *released* figures are privatized; the model itself
        # is untouched. The metrics leave here noised, and everything
        # downstream (reports, deployment attestations) sees only the
        # DP values.
        num_test = sum(len(p.y_test) for p in partitions)
        reporter = DPMetricsReporter(
            epsilon_per_query=dp_cfg["epsilon_per_query"], num_examples=num_test
        )
        final = reporter.privatize(final)
        final["dp_epsilon_spent"] = reporter.epsilon_spent
        logger.info("DP-released test metrics: %s", format_metrics(final))

    return final


def _evaluate_globally(
    weights: list[np.ndarray], partitions: list[HospitalPartition], config: dict
) -> dict[str, float]:
    """Score the global model on all clients' test data pooled together.

    Pooling only the predictions, never the training data, makes this
    directly comparable with the centralised baseline.
    """
    model = SepsisModel(
        input_dim=partitions[0].num_features,
        hidden_layers=tuple(config["model"]["hidden_layers"]),
    )
    set_parameters(model, weights)
    model.eval()

    x_test = np.vstack([p.x_test for p in partitions])
    y_test = np.concatenate([p.y_test for p in partitions])
    with torch.no_grad():
        probabilities = model(torch.tensor(x_test, dtype=torch.float32)).squeeze(1)
    return compute_metrics(y_test, probabilities.numpy())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    ()
