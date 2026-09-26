"""Local (centralised) sepsis model training.

This is step one of the supervisor's prototype sequence: get a single
model predicting sepsis on pooled data before anything is federated.
The result is the baseline that the federated run is compared against -
pooling every hospital's data is exactly what GDPR makes difficult, so
this baseline represents the "best case that we are not allowed to
have" in the real world.

Run directly to train and report metrics::

    python -m training.local_training
"""

import logging
from pathlib import Path

import numpy as np
import torch
import yaml
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from models.sepsis_model import SepsisModel, count_parameters
from preprocessing.partition_by_hospital import build_partitions
from training.metrics import compute_metrics, format_metrics

logger = logging.getLogger(__name__)

FL_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
TRAINING_CONFIG_PATH = FL_PIPELINE_ROOT / "config" / "training_config.yaml"


def load_training_config(path: str | Path = TRAINING_CONFIG_PATH) -> dict:
    """Read the training configuration."""
    with open(path) as fh:
        return yaml.safe_load(fh)


def make_loader(
    x: np.ndarray, y: np.ndarray, batch_size: int, shuffle: bool
) -> DataLoader:
    """Wrap feature and label arrays in a DataLoader."""
    dataset = TensorDataset(
        torch.tensor(x, dtype=torch.float32),
        torch.tensor(y, dtype=torch.float32).unsqueeze(1),
    )
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def train_epochs(
    model: nn.Module,
    loader: DataLoader,
    epochs: int,
    learning_rate: float,
    pos_weight: float | None = None,
) -> float:
    """Train a model in place and return the mean loss of the last epoch.

    Args:
        model: the model to train.
        loader: training batches.
        epochs: number of passes over the data.
        learning_rate: Adam learning rate.
        pos_weight: optional weight on the positive class, used to
            counteract the roughly 6:1 class imbalance.

    Returns:
        Mean loss across the final epoch.
    """
    weight = None if pos_weight is None else torch.tensor([pos_weight])
    criterion = nn.BCELoss(reduction="none")
    optimiser = torch.optim.Adam(model.parameters(), lr=learning_rate)

    model.train()
    mean_loss = 0.0
    for epoch in range(epochs):
        losses = []
        for features, labels in loader:
            optimiser.zero_grad()
            predictions = model(features)
            loss = criterion(predictions, labels)
            if weight is not None:
                # Upweight positives: sepsis cases are the minority.
                loss = loss * (1 + (weight - 1) * labels)
            loss = loss.mean()
            loss.backward()
            optimiser.step()
            losses.append(loss.item())
        mean_loss = float(np.mean(losses))
        logger.debug("epoch %d/%d loss=%.4f", epoch + 1, epochs, mean_loss)
    return mean_loss


def evaluate(model: nn.Module, x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Score a trained model on held-out data."""
    model.eval()
    with torch.no_grad():
        probabilities = model(torch.tensor(x, dtype=torch.float32)).squeeze(1)
    return compute_metrics(y, probabilities.numpy())


def pooled_dataset(
    partitions: list,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Concatenate every client's data - the centralised baseline.

    In a real deployment this pooling is precisely what data protection
    law restricts; here it establishes the upper-bound comparison.
    """
    x_train = np.vstack([p.x_train for p in partitions])
    y_train = np.concatenate([p.y_train for p in partitions])
    x_test = np.vstack([p.x_test for p in partitions])
    y_test = np.concatenate([p.y_test for p in partitions])
    return x_train, y_train, x_test, y_test


def run_local_training(seed: int = 42) -> dict[str, float]:
    """Train the centralised baseline and return its test metrics."""
    torch.manual_seed(seed)
    config = load_training_config()
    local = config["local_training"]

    partitions = build_partitions()
    x_train, y_train, x_test, y_test = pooled_dataset(partitions)
    logger.info(
        "Centralised baseline: %d train / %d test stays, %.1f%% sepsis",
        len(x_train),
        len(x_test),
        100 * y_train.mean(),
    )

    model = SepsisModel(
        input_dim=x_train.shape[1],
        hidden_layers=tuple(config["model"]["hidden_layers"]),
    )
    logger.info("Model has %d trainable parameters", count_parameters(model))

    # One epoch count that matches the federated budget: the federated
    # run does epochs_per_round on each of num_rounds rounds.
    epochs = local["epochs_per_round"] * config["fl"]["num_rounds"]
    pos_weight = float((y_train == 0).sum() / max((y_train == 1).sum(), 1))

    loader = make_loader(x_train, y_train, local["batch_size"], shuffle=True)
    final_loss = train_epochs(
        model, loader, epochs, local["learning_rate"], pos_weight
    )

    metrics = evaluate(model, x_test, y_test)
    logger.info("Final training loss %.4f", final_loss)
    logger.info("Centralised test metrics: %s", format_metrics(metrics))
    return metrics


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    run_local_training()
