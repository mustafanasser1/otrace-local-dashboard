"""Validation-based threshold selection for the OTrace-FL sepsis prototype.

This experiment leaves the existing prototype untouched.

Design
------
1. Rebuild the same three hospital-group FL clients.
2. Split each group by PATIENT into 60% train / 20% validation / 20% test.
3. Fit imputation/scaling on TRAIN only, then apply it to validation and test.
4. Train the same FL model for the configured 10 rounds / 3 local epochs.
5. Select a decision threshold using VALIDATION data only (highest F1).
6. Evaluate exactly once on the untouched TEST data at:
   a) the existing default threshold 0.50, and
   b) the validation-selected threshold.

Run from the fl-pipeline directory:
    py validation_threshold_experiment.py
"""

from dataclasses import dataclass
import numpy as np
import torch

from models.sepsis_model import SepsisModel, get_parameters, set_parameters
from preprocessing.feature_extraction import build_feature_matrix, feature_columns
from preprocessing.sepsis_labelling import build_labelled_cohort
from preprocessing.load_eicu import load_config
from preprocessing.partition_by_hospital import (
    HospitalPartition,
    assign_hospitals_to_groups,
)
from training.federated_training import HospitalClient
from training.local_training import load_training_config
from training.metrics import compute_metrics
from training.secure_aggregation import PairwiseMasker, secure_aggregate


@dataclass
class EvalSplit:
    x_val: np.ndarray
    y_val: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray


def _three_way_patient_split(frame, validation_fraction, test_fraction, seed):
    """Patient-safe train/validation/test split."""
    patients = frame["uniquepid"].unique()
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(patients)

    n_test = int(round(len(shuffled) * test_fraction))
    n_val = int(round(len(shuffled) * validation_fraction))

    test_patients = set(shuffled[:n_test])
    val_patients = set(shuffled[n_test:n_test + n_val])

    is_test = frame["uniquepid"].isin(test_patients)
    is_val = frame["uniquepid"].isin(val_patients)

    test = frame[is_test]
    val = frame[is_val]
    train = frame[~(is_test | is_val)]
    return train, val, test


def _impute_and_scale_three(train, val, test):
    """Fit preprocessing on training data only; transform val/test with it."""
    with np.errstate(all="ignore"):
        medians = np.nanmedian(train, axis=0)
    medians = np.where(np.isnan(medians), 0.0, medians)

    train_filled = np.where(np.isnan(train), medians, train)
    val_filled = np.where(np.isnan(val), medians, val)
    test_filled = np.where(np.isnan(test), medians, test)

    mean = train_filled.mean(axis=0)
    std = train_filled.std(axis=0)
    std[std == 0] = 1.0

    return (
        (train_filled - mean) / std,
        (val_filled - mean) / std,
        (test_filled - mean) / std,
    )


def build_train_val_test_partitions(validation_fraction=0.20, test_fraction=0.20):
    """Build 3 FL clients with patient-safe 60/20/20 splits."""
    data_cfg = load_config()
    settings = data_cfg["partitioning"]
    seed = settings["random_seed"]

    matrix = build_feature_matrix(build_labelled_cohort())
    columns = feature_columns(matrix)
    groups = assign_hospitals_to_groups(matrix, settings["num_groups"])

    train_partitions = []
    eval_splits = []

    for group_id, hospital_ids in groups.items():
        rows = matrix[matrix["hospitalid"].isin(hospital_ids)]
        train, val, test = _three_way_patient_split(
            rows,
            validation_fraction=validation_fraction,
            test_fraction=test_fraction,
            seed=seed + group_id,
        )

        x_train, x_val, x_test = _impute_and_scale_three(
            train[columns].to_numpy(dtype=float),
            val[columns].to_numpy(dtype=float),
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
        train_partitions.append(partition)
        eval_splits.append(
            EvalSplit(
                x_val=x_val,
                y_val=val["sepsis"].to_numpy(dtype=float),
                x_test=x_test,
                y_test=test["sepsis"].to_numpy(dtype=float),
            )
        )

    return train_partitions, eval_splits


def _predict(weights, partitions, config, split_name):
    """Pool predictions only for validation or test evaluation."""
    model = SepsisModel(
        input_dim=partitions[0].x_val.shape[1],
        hidden_layers=tuple(config["model"]["hidden_layers"]),
    )
    set_parameters(model, weights)
    model.eval()

    if split_name == "validation":
        x = np.vstack([p.x_val for p in partitions])
        y = np.concatenate([p.y_val for p in partitions])
    elif split_name == "test":
        x = np.vstack([p.x_test for p in partitions])
        y = np.concatenate([p.y_test for p in partitions])
    else:
        raise ValueError("split_name must be 'validation' or 'test'")

    with torch.no_grad():
        probabilities = model(torch.tensor(x, dtype=torch.float32)).squeeze(1).numpy()
    return y, probabilities


def train_federated_for_experiment(seed=42):
    """Train the same FL model and return final weights plus val/test splits."""
    torch.manual_seed(seed)
    config = load_training_config()
    partitions, eval_splits = build_train_val_test_partitions()

    clients = [HospitalClient(p, config, trace_logger=None) for p in partitions]
    global_weights = clients[0].get_parameters()

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

    rounds = config["fl"]["num_rounds"]
    print(
        f"Training: {len(clients)} clients, {rounds} rounds, "
        f"{config['local_training']['epochs_per_round']} local epochs/round"
    )

    for server_round in range(1, rounds + 1):
        updates = [client.fit(global_weights)[:2] for client in clients]

        if not use_secure:
            # Plain weighted FedAvg for completeness if secure aggregation is disabled.
            counts = [n for _, n in updates]
            total = sum(counts)
            global_weights = [
                sum(n * w[layer] for w, n in updates) / total
                for layer in range(len(updates[0][0]))
            ]
        else:
            masked = [
                masker.mask_update(weights, num_examples, server_round)
                for masker, (weights, num_examples) in zip(maskers, updates)
            ]
            counts = [num_examples for _, num_examples in updates]
            global_weights = secure_aggregate(masked, counts)

        print(f"  round {server_round:2d}/{rounds} complete")

    return global_weights, eval_splits, config


def main():
    weights, splits, config = train_federated_for_experiment(seed=42)

    y_val, p_val = _predict(weights, splits, config, "validation")
    y_test, p_test = _predict(weights, splits, config, "test")

    print("\nData split")
    print("-" * 72)
    print(f"Validation cases: {len(y_val)} | Sepsis: {100*y_val.mean():.1f}%")
    print(f"Test cases:       {len(y_test)} | Sepsis: {100*y_test.mean():.1f}%")

    # Fine enough for a prototype experiment while remaining easy to explain.
    thresholds = np.arange(0.10, 0.901, 0.01)
    validation_results = [
        (float(t), compute_metrics(y_val, p_val, threshold=float(t)))
        for t in thresholds
    ]
    selected_threshold, selected_val = max(
        validation_results, key=lambda item: item[1]["f1"]
    )

    baseline_test = compute_metrics(y_test, p_test, threshold=0.50)
    selected_test = compute_metrics(y_test, p_test, threshold=selected_threshold)

    print("\nThreshold selected on VALIDATION only")
    print("-" * 72)
    print(f"Selected threshold: {selected_threshold:.2f}")
    print(
        "Validation metrics: "
        f"accuracy={selected_val['accuracy']:.3f}  "
        f"auc={selected_val['auc']:.3f}  "
        f"precision={selected_val['precision']:.3f}  "
        f"recall={selected_val['recall']:.3f}  "
        f"f1={selected_val['f1']:.3f}"
    )

    print("\nFINAL evaluation on untouched TEST set")
    print("-" * 72)
    print("Metric        threshold=0.50   selected threshold")
    for metric in ["accuracy", "auc", "precision", "recall", "f1"]:
        print(
            f"{metric:<12}  {baseline_test[metric]:>8.3f}"
            f"            {selected_test[metric]:>8.3f}"
        )

    print("\nResearch interpretation")
    print("- Threshold was chosen using validation data, not test data.")
    print("- Test data remained untouched until the final comparison.")
    print("- AUC should be identical across thresholds because ranking is unchanged.")
    print("- Precision/recall/F1 may trade off as the decision threshold changes.")


if __name__ == "__main__":
    main()
