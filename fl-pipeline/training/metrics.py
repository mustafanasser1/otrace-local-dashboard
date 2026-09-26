"""Evaluation metrics shared by local and federated training."""

import logging

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)

#: Decision threshold for turning probabilities into labels.
DEFAULT_THRESHOLD = 0.5


def compute_metrics(
    y_true: np.ndarray, y_prob: np.ndarray, threshold: float = DEFAULT_THRESHOLD
) -> dict[str, float]:
    """Score predictions against the configured metric set.

    Args:
        y_true: binary ground-truth labels.
        y_prob: predicted probabilities.
        threshold: probability above which a case counts as positive.

    Returns:
        Mapping of metric name to value. AUC is NaN when the evaluation
        set happens to contain a single class, which can occur for a
        small client's test split.
    """
    y_pred = (y_prob >= threshold).astype(int)
    single_class = len(np.unique(y_true)) < 2

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "auc": float("nan") if single_class else float(roc_auc_score(y_true, y_prob)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
    }


def format_metrics(metrics: dict[str, float]) -> str:
    """One-line rendering for logs."""
    return "  ".join(f"{name}={value:.3f}" for name, value in metrics.items())
