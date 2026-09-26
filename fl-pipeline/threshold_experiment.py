"""
Threshold experiment for the OTrace-FL prototype.

Purpose:
- Run the existing federated training once.
- Capture the pooled final-model y_true / y_prob passed to compute_metrics().
- Recalculate metrics at several decision thresholds.
- Does NOT modify the original prototype files.

Important:
This is an exploratory threshold analysis on the current pooled test set.
For a final research evaluation, choose/tune the threshold on validation data
and report final performance on a separate untouched test set.
"""

import numpy as np
import training.federated_training as ft
from training.metrics import compute_metrics as original_compute_metrics

captured = {"y_true": None, "y_prob": None}


def capture_compute_metrics(y_true, y_prob, threshold=0.5):
    """Keep the largest evaluation set, which is the pooled final evaluation."""
    y_true_arr = np.asarray(y_true)
    y_prob_arr = np.asarray(y_prob)

    if captured["y_true"] is None or len(y_true_arr) > len(captured["y_true"]):
        captured["y_true"] = y_true_arr.copy()
        captured["y_prob"] = y_prob_arr.copy()

    return original_compute_metrics(y_true_arr, y_prob_arr, threshold=threshold)


# Temporarily replace the function used inside federated_training.py.
ft.compute_metrics = capture_compute_metrics

print("Running federated training once...")
baseline = ft.run_federated_training(trace_logger=None, seed=42)

if captured["y_true"] is None:
    raise RuntimeError("Could not capture final evaluation probabilities.")

y_true = captured["y_true"]
y_prob = captured["y_prob"]

print(f"\nCaptured pooled evaluation set: {len(y_true)} cases")
print("\nThreshold experiment")
print("-" * 76)
print(f"{'Threshold':>9} {'Accuracy':>10} {'AUC':>8} {'Precision':>11} {'Recall':>9} {'F1':>9}")
print("-" * 76)

thresholds = np.arange(0.20, 0.61, 0.05)
results = []

for threshold in thresholds:
    m = original_compute_metrics(y_true, y_prob, threshold=float(threshold))
    results.append((float(threshold), m))
    print(
        f"{threshold:9.2f} "
        f"{m['accuracy']:10.3f} "
        f"{m['auc']:8.3f} "
        f"{m['precision']:11.3f} "
        f"{m['recall']:9.3f} "
        f"{m['f1']:9.3f}"
    )

best_threshold, best_metrics = max(results, key=lambda item: item[1]["f1"])

print("-" * 76)
print(
    f"Highest exploratory F1 in this grid: threshold={best_threshold:.2f}, "
    f"F1={best_metrics['f1']:.3f}, "
    f"Precision={best_metrics['precision']:.3f}, "
    f"Recall={best_metrics['recall']:.3f}"
)
print("\nBaseline returned by the prototype at its default threshold:")
print(baseline)
print(
    "\nNOTE: Treat the 'highest F1' result as exploratory only. "
    "For the thesis, threshold selection should be performed on validation data, "
    "then evaluated once on an untouched test set."
)
