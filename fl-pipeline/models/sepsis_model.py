"""The sepsis prediction model.

A small feed-forward network, exactly as the prototype spec defines it.
This is deliberately simple: the thesis contribution is the traceability
and validation layer around training, not the classifier itself. A
logistic regression would serve equally well.
"""

import logging

import numpy as np
import torch
from torch import nn

logger = logging.getLogger(__name__)


class SepsisModel(nn.Module):
    """Binary classifier over the per-stay feature vector.

    Args:
        input_dim: number of input features.
        hidden_layers: sizes of the two hidden layers.
        dropout: dropout probability applied after each hidden layer.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_layers: tuple[int, int] = (64, 32),
        dropout: float = 0.2,
    ):
        super().__init__()
        first, second = hidden_layers
        self.fc1 = nn.Linear(input_dim, first)
        self.fc2 = nn.Linear(first, second)
        self.fc3 = nn.Linear(second, 1)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Return the sepsis probability for each row of ``x``."""
        x = self.dropout(self.relu(self.fc1(x)))
        x = self.dropout(self.relu(self.fc2(x)))
        return self.sigmoid(self.fc3(x))


def get_parameters(model: nn.Module) -> list[np.ndarray]:
    """Model weights as a list of arrays, in state_dict order.

    This is the exchange format Flower uses to move updates between
    clients and server.

    The arrays are copies. ``Tensor.numpy()`` would otherwise share
    memory with the model, so a previously returned update would mutate
    in place the next time that client trained - a client's round-3
    contribution could silently become its round-4 weights.
    """
    return [value.cpu().numpy().copy() for value in model.state_dict().values()]


def set_parameters(model: nn.Module, parameters: list[np.ndarray]) -> None:
    """Load weights produced by :func:`get_parameters` back into a model."""
    state_dict = dict(
        zip(
            model.state_dict().keys(),
            (torch.tensor(p) for p in parameters),
            strict=True,
        )
    )
    model.load_state_dict(state_dict)


def count_parameters(model: nn.Module) -> int:
    """Total number of trainable parameters - reported in trace metadata."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
