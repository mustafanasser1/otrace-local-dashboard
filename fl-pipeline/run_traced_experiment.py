"""End-to-end traced federated learning experiment.

Runs the whole prototype in one pass and prints what a compliance
reviewer would want to see:

1. Declare the parties and their GDPR roles.
2. Establish patient consent before any data is touched.
3. Verify a data use against live consent.
4. Train the sepsis model federatively, attesting every lifecycle event.
5. Attest the deployment of the resulting model.
6. Process a right-to-erasure request and report what it could and
   could not undo.
7. Summarise trace completeness and instrumentation overhead.

Requires the OTrace service to be running::

    cd otrace-service && python -m uvicorn main:app --port 8080
    cd fl-pipeline && python run_traced_experiment.py
"""

import argparse
import logging
import statistics
import time

from otrace_integration.consent_manager import ConsentManager
from otrace_integration.erasure_handler import ErasureHandler
from otrace_integration.event_logger import (
    AGGREGATION,
    DEPLOYMENT,
    LOCAL_TRAINING,
    UPDATE_SUBMISSION,
    FLEventLogger,
)
from otrace_integration.otrace_client import OTraceClient, OTraceUnavailableError
from otrace_integration.role_declaration import declare_all_roles
from preprocessing.partition_by_hospital import build_partitions
from training.federated_training import run_federated_training
from training.local_training import load_training_config
from training.metrics import format_metrics

logger = logging.getLogger(__name__)


#: Paired repetitions used for the overhead measurement.
OVERHEAD_REPEATS = 5


def _heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


def measure_overhead(
    client: OTraceClient, registry, num_groups: int, seed: int
) -> tuple[float, float, float]:
    """Measure what tracing costs, as a median of paired runs.

    Timing a single traced run against a single untraced one is not
    reliable here. The first run of the process pays for imports, data
    loading and torch initialisation, so whichever run goes first looks
    slower - an earlier version of this function timed the traced run
    first and the untraced run last, and reported overheads between
    -27% and +46% on identical code. Negative overhead is impossible,
    which is what gave the error away.

    So: warm up once, then alternate untraced and traced runs and take
    the median of each.

    Returns:
        ``(untraced_median, traced_median, overhead_percent)``.
    """
    run_federated_training(trace_logger=None, seed=seed)  # warm-up, discarded

    untraced, traced = [], []
    for repeat in range(OVERHEAD_REPEATS):
        started = time.perf_counter()
        run_federated_training(trace_logger=None, seed=seed)
        untraced.append(time.perf_counter() - started)

        # A fresh logger each time so attestation counts stay comparable.
        logger_ = FLEventLogger(client, registry, num_groups=num_groups)
        started = time.perf_counter()
        run_federated_training(trace_logger=logger_, seed=seed)
        traced.append(time.perf_counter() - started)

    untraced_median = statistics.median(untraced)
    traced_median = statistics.median(traced)
    overhead = (traced_median - untraced_median) / untraced_median * 100
    return untraced_median, traced_median, overhead


def run_experiment(consent_sample: int = 60, seed: int = 42) -> dict:
    """Run the full traced experiment.

    Args:
        consent_sample: how many patients to establish consent for.
            Every patient would take several minutes of REST calls and
            demonstrates nothing further, so a sample is used and the
            reduction is reported rather than hidden.
        seed: seed for reproducible training.

    Returns:
        A summary mapping with metrics, event counts, and timings.
    """
    client = OTraceClient()
    if not client.is_available():
        raise OTraceUnavailableError(
            "OTrace service is not running. Start it with:\n"
            "  cd otrace-service && python -m uvicorn main:app --port 8080"
        )

    config = load_training_config()
    num_groups = config["fl"]["num_clients"]
    partitions = build_partitions()

    # 1. Roles ----------------------------------------------------------
    _heading("1. Parties and GDPR roles")
    for role in declare_all_roles(num_groups):
        print(
            f"  {role.party_name:20s} {role.gdpr_role:18s} "
            f"{role.gdpr_article:12s} (OTrace: {role.otrace_data_controller})"
        )

    # 2. Consent --------------------------------------------------------
    _heading("2. Patient consent")
    all_patients = sorted({p for part in partitions for p in part.patient_ids})
    sample = all_patients[:consent_sample]
    manager = ConsentManager(client)

    started = time.perf_counter()
    registry = manager.establish_all(sample)
    consent_seconds = time.perf_counter() - started
    print(
        f"  Consent established for {len(registry)} of {len(all_patients)} "
        f"patients in {consent_seconds:.1f}s"
    )
    if len(sample) < len(all_patients):
        print(
            f"  NOTE: sampled {len(sample)} patients to keep the demo short. "
            "The remaining patients are untouched, not silently consented."
        )

    # 3. Verify a use against live consent ------------------------------
    _heading("3. Runtime consent check")
    verdict = manager.verify_data_use(sample[0])
    print(f"  Data use by {sample[0]}: valid={verdict['valid']} - {verdict['message']}")

    # 4. Traced federated training --------------------------------------
    _heading("4. Federated training, fully traced")
    event_logger = FLEventLogger(client, registry, num_groups=num_groups)

    started = time.perf_counter()
    metrics = run_federated_training(trace_logger=event_logger, seed=seed)
    traced_seconds = time.perf_counter() - started
    print(f"  Final model: {format_metrics(metrics)}")

    # 5. Deployment -----------------------------------------------------
    _heading("5. Model deployment")
    deployment = event_logger.log_deployment("sepsis-fl-v1.0", metrics)
    print(f"  Deployment attested: {deployment['id']}")

    # 6. Erasure --------------------------------------------------------
    _heading("6. Right to erasure (Article 17)")
    handler = ErasureHandler(client, manager, event_logger)
    subject = sample[0]
    outcome = handler.handle_erasure_request(subject, partitions)
    print(f"  {outcome.summary()}")
    print(f"  {outcome.notes}")
    print(f"  Verified no live consent remains: {handler.verify_erasure(subject)}")

    # 7. Trace completeness ---------------------------------------------
    _heading("7. Trace completeness")
    rounds = config["fl"]["num_rounds"]
    expected = {
        LOCAL_TRAINING: num_groups * rounds,
        UPDATE_SUBMISSION: num_groups * rounds,
        AGGREGATION: rounds,
        DEPLOYMENT: 1,
    }
    actual = event_logger.event_counts()
    complete = True
    for event_type, count in expected.items():
        got = actual.get(event_type, 0)
        mark = "OK " if got == count else "MISS"
        complete &= got == count
        print(f"  [{mark}] {event_type:22s} expected {count:3d}  recorded {got:3d}")
    print(f"  Total attestations: {len(event_logger.recorded)}")
    print(f"  Trace complete: {complete}")

    # Overhead ----------------------------------------------------------
    _heading("8. Instrumentation overhead")
    untraced_seconds, measured_traced, overhead = measure_overhead(
        client, registry, num_groups, seed
    )
    print(f"  Untraced run (median of {OVERHEAD_REPEATS}): {untraced_seconds:.2f}s")
    print(f"  Traced run   (median of {OVERHEAD_REPEATS}): {measured_traced:.2f}s")
    print(
        f"  Overhead: {overhead:+.1f}%  "
        f"({(measured_traced - untraced_seconds) / max(len(event_logger.recorded), 1) * 1000:.1f}"
        f" ms per attestation)"
    )

    return {
        "metrics": metrics,
        "event_counts": actual,
        "trace_complete": complete,
        "traced_seconds": measured_traced,
        "untraced_seconds": untraced_seconds,
        "first_traced_seconds": traced_seconds,
        "overhead_percent": overhead,
        "consents": len(registry),
        "erasure": outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--consent-sample",
        type=int,
        default=60,
        help="number of patients to establish consent for (default: 60)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_experiment(consent_sample=args.consent_sample, seed=args.seed)
    print("\nExperiment complete.\n")


if __name__ == "__main__":
    main()
