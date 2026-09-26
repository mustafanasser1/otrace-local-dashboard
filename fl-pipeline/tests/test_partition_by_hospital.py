"""Tests for hospital grouping and patient-safe train/test splitting."""

import numpy as np
import pandas as pd
import pytest

from preprocessing.load_eicu import data_dir
from preprocessing.partition_by_hospital import (
    assign_hospitals_to_groups,
    build_partitions,
    split_by_patient,
)


@pytest.fixture
def cohort() -> pd.DataFrame:
    # Hospital sizes 10, 8, 6, 4, 2 across 30 stays.
    rows = []
    for hospital_id, size in [(1, 10), (2, 8), (3, 6), (4, 4), (5, 2)]:
        rows += [{"hospitalid": hospital_id} for _ in range(size)]
    return pd.DataFrame(rows)


def test_every_hospital_assigned_exactly_once(cohort):
    groups = assign_hospitals_to_groups(cohort, num_groups=3)
    assigned = [h for ids in groups.values() for h in ids]
    assert sorted(assigned) == [1, 2, 3, 4, 5]
    assert len(assigned) == len(set(assigned))


def test_groups_are_size_balanced(cohort):
    groups = assign_hospitals_to_groups(cohort, num_groups=3)
    sizes = cohort.groupby("hospitalid").size()
    totals = [sum(sizes[h] for h in ids) for ids in groups.values()]
    # Greedy largest-first keeps the spread tight: 10 / 10 / 10 here.
    assert max(totals) - min(totals) <= 2


def test_split_by_patient_never_splits_a_patient():
    frame = pd.DataFrame(
        {
            "uniquepid": ["a", "a", "b", "c", "d", "e", "f", "g", "h", "i"],
            "value": range(10),
        }
    )
    train, test = split_by_patient(frame, test_fraction=0.3, seed=1)
    assert set(train["uniquepid"]) & set(test["uniquepid"]) == set()
    assert len(train) + len(test) == len(frame)


def test_split_by_patient_is_deterministic():
    frame = pd.DataFrame({"uniquepid": list("abcdefghij"), "value": range(10)})
    first = split_by_patient(frame, 0.2, seed=7)[1]["uniquepid"].tolist()
    second = split_by_patient(frame, 0.2, seed=7)[1]["uniquepid"].tolist()
    assert first == second


@pytest.mark.skipif(
    not data_dir().exists(), reason="eICU demo dataset not present"
)
def test_real_partitions_are_balanced_and_usable():
    """Integration check: three viable, comparable FL clients."""
    partitions = build_partitions()
    assert len(partitions) == 3

    for p in partitions:
        assert p.num_features == 74
        assert len(p.x_train) > 300 and len(p.x_test) > 50
        # Every client needs enough positives to learn from.
        assert 0.10 <= p.y_train.mean() <= 0.22
        assert p.y_test.sum() > 0
        # Scaling must leave finite values for the optimiser.
        assert np.isfinite(p.x_train).all() and np.isfinite(p.x_test).all()

    # No hospital appears in two groups.
    all_hospitals = [h for p in partitions for h in p.hospital_ids]
    assert len(all_hospitals) == len(set(all_hospitals)) == 186

    # Clients should be of comparable size for a fair FedAvg comparison.
    sizes = [len(p.x_train) for p in partitions]
    assert max(sizes) - min(sizes) < 0.2 * max(sizes)
