"""Consumer side: the stream is enriched into GDPR attestations.

The consumer reads the raw lifecycle facts the producer published and
hands each to an ``FLEventLogger``, which adds what accountability
requires - consent references, legal basis, purpose, controller roles -
and writes the attestation to OTrace. Because Kafka retains the log,
the same stream can be consumed again from the beginning: a replay
yields the identical event sequence, which is what makes experiments
reproducible after the fact.
"""

import logging

from kafka import KafkaConsumer

from streaming.event_stream import deserialize, load_streaming_config

logger = logging.getLogger(__name__)


class AttestationConsumer:
    """Drains a run's topic and turns facts into attestations.

    Args:
        topic: the experiment run's topic.
        config: parsed streaming configuration.
    """

    def __init__(self, topic: str, config: dict | None = None):
        self.config = config or load_streaming_config()
        self.topic = topic

    def _consumer(self) -> KafkaConsumer:
        return KafkaConsumer(
            self.topic,
            bootstrap_servers=self.config["bootstrap_servers"],
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            group_id=None,  # no committed offsets: every drain starts at 0
            consumer_timeout_ms=self.config["consumer_timeout_ms"],
            value_deserializer=deserialize,
        )

    def read_events(self) -> list[dict]:
        """Every event on the topic, in log order."""
        consumer = self._consumer()
        try:
            return [message.value for message in consumer]
        finally:
            consumer.close()

    def enrich_into(self, event_logger) -> dict[str, int]:
        """Replay the stream through an FLEventLogger, attesting each fact.

        Returns:
            Count of events dispatched per event type.
        """
        dispatched: dict[str, int] = {}
        for event in self.read_events():
            kind = event["event"]
            if kind == "LocalTrainingEvent":
                event_logger.log_local_training(
                    event["group_id"], event["server_round"], event["metrics"]
                )
            elif kind == "UpdateSubmissionEvent":
                event_logger.log_update_submission(
                    event["group_id"], event["server_round"], event["num_examples"]
                )
            elif kind == "AggregationEvent":
                event_logger.log_aggregation(
                    event["server_round"], event["num_clients"], event["metrics"]
                )
            elif kind == "DeploymentEvent":
                event_logger.log_deployment(event["model_version"], event["metrics"])
            else:  # unknown facts are surfaced, not silently dropped
                logger.warning("unrecognised event on %s: %r", self.topic, kind)
                continue
            dispatched[kind] = dispatched.get(kind, 0) + 1
        logger.info("enriched %s: %s", self.topic, dispatched)
        return dispatched
