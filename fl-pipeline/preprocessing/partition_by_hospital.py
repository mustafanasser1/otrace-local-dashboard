"""Partition the eICU cohort into federated learning clients.

The eICU demo spreads 1,627 cohort stays across 186 hospitals, the
largest holding only 21. Individual hospitals are therefore too small to
be useful FL clients, so they are grouped into balanced consortia - each
group becomes one client, and each still represents a set of hospitals
acting as joint controllers under GDPR Article 26.

Two invariants matter here:

* **Grouping is by hospital.** A hospital never spans two groups, so the
  controller relationship stays clean.
* **Splitting is by patient.** A handful of patients have stays in more
  than one hospital, and several have repeat stays; splitting on stays
  would put the same person in both train and test and inflate results.
"""

import logging

import numpy as np
import pandas as pd

from preprocessing.feature_extraction import (
    build_feature_matrix,
    feature_columns,
    impute_and_scale,
)
from preprocessing.load_eicu import load_config
from preprocessing.sepsis_labelling import build_labelled_cohort

logger = logging.getLogger(__name__)


class HospitalPartition:
    """One federated client: a group of hospitals with split, scaled data.

    Attributes:
        group_id: zero-based client index.
        hospital_ids: the hospitals assigned to this group.
        x_train, y_train, x_test, y_test: model-ready arrays.
        patient_ids: every ``uniquepid`` in the group, used by the
            erasure flow to locate a data subject's records.
    """

    def __init__(
        self,
        group_id: int,
        hospital_ids: list[int],
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_test: np.ndarray,
        y_test: np.ndarray,
        patient_ids: list[str],
    ):
        self.group_id = group_id
        self.hospital_ids = hospital_ids
        self.x_train = x_train
        self.y_train = y_train
        self.x_test = x_test
        self.y_test = y_test
        self.patient_ids = patient_ids

    @property
    def num_features(self) -> int:
        return self.x_train.shape[1]

    def __repr__(self) -> str:
        return (
            f"<HospitalPartition {self.group_id}: "
            f"{len(self.hospital_ids)} hospitals, "
            f"{len(self.x_train)} train / {len(self.x_test)} test, "
            f"{self.y_train.mean():.1%} sepsis>"
        )


def assign_hospitals_to_groups(
    cohort: pd.DataFrame, num_groups: int
) -> dict[int, list[int]]:
    """Greedily balance hospitals across groups by stay count.

    Hospitals are sorted largest first and each is handed to whichever
    group currently holds the fewest stays. This balances better than
    plain round-robin when hospital sizes vary.

    Args:
        cohort: labelled cohort with a ``hospitalid`` column.
        num_groups: number of FL clients to create.

    Returns:
        Mapping of group index to its list of hospital ids.
    """
    sizes = cohort.groupby("hospitalid").size().sort_values(ascending=False)
    groups: dict[int, list[int]] = {g: [] for g in range(num_groups)}
    totals = dict.fromkeys(range(num_groups), 0)

    for hospital_id, size in sizes.items():
        target = min(totals, key=totals.get)
        groups[target].append(int(hospital_id))
        totals[target] += size

    logger.info(
        "Assigned %d hospitals to %d groups, stays per group: %s",
        len(sizes),
        num_groups,
        list(totals.values()),
    )
    return groups


def split_by_patient(
    frame: pd.DataFrame, test_fraction: float, seed: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a group's stays into train and test without splitting a patient.

    Args:
        frame: feature rows for one group, with a ``uniquepid`` column.
        test_fraction: share of patients to hold out.
        seed: seed for the shuffle.

    Returns:
        ``(train, test)`` frames.
    """
    patients = frame["uniquepid"].unique()
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(patients)
    cut = int(round(len(shuffled) * test_fraction))
    test_patients = set(shuffled[:cut])

    is_test = frame["uniquepid"].isin(test_patients)
    return frame[~is_test], frame[is_test]


def build_partitions() -> list[HospitalPartition]:
    """Build every federated client from the raw dataset.

    Each group is imputed and scaled with its own statistics, matching
    the federated setting where a client cannot see other clients' data.

    Returns:
        One :class:`HospitalPartition` per group, ordered by group id.
    """
    config = load_config()
    settings = config["partitioning"]

    matrix = build_feature_matrix(build_labelled_cohort())
    columns = feature_columns(matrix)
    groups = assign_hospitals_to_groups(matrix, settings["num_groups"])

    partitions = []
    for group_id, hospital_ids in groups.items():
        rows = matrix[matrix["hospitalid"].isin(hospital_ids)]
        train, test = split_by_patient(
            rows, settings["test_fraction"], settings["random_seed"] + group_id
        )

        x_train, x_test = impute_and_scale(
            train[columns].to_numpy(dtype=float),
            test[columns].to_numpy(dtype=float),
        )
        partition = HospitalPartition(
            group_id=group_id,
            hospital_ids=hospital_ids,
            x_train=x_train,
            y_train=train["sepsis"].to_numpy(dtype=float),
            x_test=x_test,
            y_test=test["sepsis"].to_numpy(dtype=float),
            patient_ids=sorted(rows["uniquepid"].unique().tolist()),
        )
        logger.info("%r", partition)
        partitions.append(partition)

    return partitions


def get_hospital_data(group_id: int) -> tuple[np.ndarray, np.ndarray]:
    """Training features and labels for one group (spec interface)."""
    partition = build_partitions()[group_id]
    return partition.x_train, partition.y_train


def get_all_hospital_partitions() -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Training data for every group, keyed by group id (spec interface)."""
    return {p.group_id: (p.x_train, p.y_train) for p in build_partitions()}
