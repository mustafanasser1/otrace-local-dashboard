"""Producer side: training publishes lifecycle facts to Kafka.

``KafkaTraceLogger`` implements the same ``TraceLogger`` protocol the
training code already accepts, so streaming replaces synchronous
attestation without touching a line of the training loop. During the
run nothing talks to OTrace at all - training's only tracing cost is a
fire-and-forget produce - and the consumer turns the stream into
attestations afterwards (or concurrently, from another process).
"""

import logging

from kafka import KafkaProducer

from streaming.event_stream import load_streaming_config, serialize

logger = logging.getLogger(__name__)


class KafkaTraceLogger:
    """Publishes training lifecycle facts to a Kafka topic.

    Args:
        topic: topic to publish to (one topic per experiment run keeps
            replays clean).
        config: parsed streaming configuration.
    """

    def __init__(self, topic: str, config: dict | None = None):
        self.config = config or load_streaming_config()
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=self.config["bootstrap_servers"],
            value_serializer=serialize,
        )
        self.published = 0

    def _publish(self, event: dict) -> None:
        self.producer.send(self.topic, event)
        self.published += 1

    # -- TraceLogger protocol ---------------------------------------------

    def log_local_training(
        self, group_id: int, server_round: int, metrics: dict
    ) -> None:
        self._publish(
            {
                "event": "LocalTrainingEvent",
                "group_id": group_id,
                "server_round": server_round,
                "metrics": {k: float(v) for k, v in metrics.items()},
            }
        )

    def log_update_submission(
        self, group_id: int, server_round: int, num_examples: int
    ) -> None:
        self._publish(
            {
                "event": "UpdateSubmissionEvent",
                "group_id": group_id,
                "server_round": server_round,
                "num_examples": int(num_examples),
            }
        )

    def log_client_round(
        self, group_id: int, server_round: int, metrics: dict, num_examples: int
    ) -> None:
        """The batched pair, streamed as its two constituent facts."""
        self.log_local_training(group_id, server_round, metrics)
        self.log_update_submission(group_id, server_round, num_examples)

    def log_aggregation(
        self, server_round: int, num_clients: int, metrics: dict
    ) -> None:
        self._publish(
            {
                "event": "AggregationEvent",
                "server_round": server_round,
                "num_clients": int(num_clients),
                "metrics": {
                    k: (float(v) if isinstance(v, (int, float)) else v)
                    for k, v in metrics.items()
                },
            }
        )

    def log_deployment(self, model_version: str, metrics: dict) -> None:
        self._publish(
            {
                "event": "DeploymentEvent",
                "model_version": model_version,
                "metrics": {k: float(v) for k, v in metrics.items()},
            }
        )

    def close(self) -> None:
        """Flush pending messages; every fact must reach the log."""
        self.producer.flush()
        self.producer.close()
        logger.info("published %d events to %s", self.published, self.topic)
