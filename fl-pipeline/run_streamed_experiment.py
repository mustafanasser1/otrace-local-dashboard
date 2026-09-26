"""Streamed federated experiment: train -> Kafka -> enrich -> attest.

The synchronous experiment (``run_traced_experiment.py``) attests every
event inline. This one decouples the two halves through Kafka:

1. Training publishes raw lifecycle facts to a per-run topic. OTrace is
   not involved at all while the model trains.
2. A consumer drains the topic, enriches each fact with the
   accountability context (consent reference, legal basis, purpose,
   GDPR role) and writes the attestations to OTrace.
3. The same topic is consumed a second time to show the log replays
   identically - the property that makes streamed experiments
   reproducible after the fact.

Requires both backing services::

    cd fl-pipeline && docker compose up -d          # Kafka
    cd otrace-service && python -m uvicorn main:app --port 8080

Then::

    cd fl-pipeline && python run_streamed_experiment.py
"""

import argparse
import logging
import time

from otrace_integration.consent_manager import ConsentManager
from otrace_integration.event_logger import (
    AGGREGATION,
    DEPLOYMENT,
    LOCAL_TRAINING,
    UPDATE_SUBMISSION,
    FLEventLogger,
)
from otrace_integration.otrace_client import OTraceClient, OTraceUnavailableError
from preprocessing.partition_by_hospital import build_partitions
from streaming.consumer import AttestationConsumer
from streaming.event_stream import load_streaming_config
from streaming.producer import KafkaTraceLogger
from training.federated_training import run_federated_training
from training.local_training import load_training_config
from training.metrics import format_metrics

logger = logging.getLogger(__name__)


def _heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


def run_streamed_experiment(consent_sample: int = 60, seed: int = 42) -> dict:
    """Run the full streamed pipeline and report each stage."""
    otrace = OTraceClient()
    if not otrace.is_available():
        raise OTraceUnavailableError(
            "OTrace service is not running. Start it with:\n"
            "  cd otrace-service && python -m uvicorn main:app --port 8080"
        )
    streaming_config = load_streaming_config()
    topic = f"{streaming_config['topic_prefix']}-{int(time.time())}"

    config = load_training_config()
    num_groups = config["fl"]["num_clients"]
    partitions = build_partitions()

    # 1. Produce ---------------------------------------------------------
    _heading("1. Training, publishing lifecycle facts to Kafka")
    print(f"  Topic: {topic}")
    producer_logger = KafkaTraceLogger(topic, streaming_config)
    started = time.perf_counter()
    metrics = run_federated_training(trace_logger=producer_logger, seed=seed)
    training_seconds = time.perf_counter() - started
    producer_logger.log_deployment("sepsis-fl-v1.0-streamed", metrics)
    producer_logger.close()
    print(f"  Final model: {format_metrics(metrics)}")
    print(
        f"  {producer_logger.published} facts published in {training_seconds:.2f}s; "
        "OTrace untouched so far"
    )

    # 2. Consent context for enrichment -----------------------------------
    _heading("2. Consent context for enrichment")
    all_patients = sorted({p for part in partitions for p in part.patient_ids})
    sample = all_patients[:consent_sample]
    manager = ConsentManager(otrace)
    registry = manager.establish_all(sample)
    print(f"  Consent on record for {len(registry)} of {len(all_patients)} patients")
    if len(sample) < len(all_patients):
        print(
            f"  NOTE: sampled {len(sample)} patients to keep the demo short. "
            "The remaining patients are untouched, not silently consented."
        )

    # 3. Consume + enrich --------------------------------------------------
    _heading("3. Consuming the stream, enriching into attestations")
    event_logger = FLEventLogger(otrace, registry, num_groups=num_groups)
    consumer = AttestationConsumer(topic, streaming_config)
    started = time.perf_counter()
    dispatched = consumer.enrich_into(event_logger)
    enrich_seconds = time.perf_counter() - started
    for kind, count in sorted(dispatched.items()):
        print(f"  {kind:22s} consumed {count:3d}")
    print(f"  {len(event_logger.recorded)} attestations written in {enrich_seconds:.2f}s")

    # 4. Completeness ------------------------------------------------------
    _heading("4. Trace completeness")
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
    print(f"  Trace complete: {complete}")

    # 5. Replay ------------------------------------------------------------
    _heading("5. Replay")
    first_read = consumer.read_events()
    second_read = consumer.read_events()
    replay_identical = first_read == second_read and len(first_read) > 0
    print(
        f"  Stream consumed twice from offset 0: {len(first_read)} events each, "
        f"identical: {replay_identical}"
    )

    return {
        "metrics": metrics,
        "topic": topic,
        "published": producer_logger.published,
        "dispatched": dispatched,
        "trace_complete": complete,
        "replay_identical": replay_identical,
        "training_seconds": training_seconds,
        "enrich_seconds": enrich_seconds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consent-sample", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_streamed_experiment(consent_sample=args.consent_sample, seed=args.seed)
    print("\nStreamed experiment complete.\n")


if __name__ == "__main__":
    main()
