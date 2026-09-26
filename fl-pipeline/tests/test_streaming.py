"""Tests for the Kafka streamed producer/consumer pipeline.

Serialization is tested without a broker. Everything that needs Kafka
is skipped when the broker is down (start it with ``docker compose up
-d`` from ``fl-pipeline/``), mirroring how the live-service OTrace
tests behave.
"""

import uuid

import pytest

from streaming.event_stream import deserialize, load_streaming_config, serialize


def _broker_up() -> bool:
    try:
        from kafka import KafkaAdminClient

        config = load_streaming_config()
        admin = KafkaAdminClient(
            bootstrap_servers=config["bootstrap_servers"], request_timeout_ms=3000
        )
        admin.close()
        return True
    except Exception:
        return False


needs_kafka = pytest.mark.skipif(not _broker_up(), reason="Kafka broker not running")


def _fresh_topic() -> str:
    return f"fl-test-{uuid.uuid4().hex[:12]}"


# -- No broker needed ------------------------------------------------------


def test_serialization_round_trips():
    event = {"event": "AggregationEvent", "server_round": 3, "metrics": {"loss": 0.4}}
    assert deserialize(serialize(event)) == event


def test_serialization_is_canonical():
    """Key order does not change the bytes - replays compare equal."""
    a = serialize({"x": 1, "event": "E"})
    b = serialize({"event": "E", "x": 1})
    assert a == b


# -- Broker required -------------------------------------------------------


@needs_kafka
def test_produce_consume_round_trip_preserves_order():
    from streaming.consumer import AttestationConsumer
    from streaming.producer import KafkaTraceLogger

    topic = _fresh_topic()
    producer = KafkaTraceLogger(topic)
    producer.log_local_training(0, 1, {"loss": 0.5, "epochs": 3})
    producer.log_update_submission(0, 1, 422)
    producer.log_aggregation(1, 3, {"total_examples": 1282})
    producer.log_deployment("v-test", {"auc": 0.75, "accuracy": 0.8})
    producer.close()

    events = AttestationConsumer(topic).read_events()
    assert [e["event"] for e in events] == [
        "LocalTrainingEvent",
        "UpdateSubmissionEvent",
        "AggregationEvent",
        "DeploymentEvent",
    ]
    assert events[1]["num_examples"] == 422


@needs_kafka
def test_client_round_streams_both_facts():
    from streaming.consumer import AttestationConsumer
    from streaming.producer import KafkaTraceLogger

    topic = _fresh_topic()
    producer = KafkaTraceLogger(topic)
    producer.log_client_round(2, 5, {"loss": 0.3, "epochs": 3}, 427)
    producer.close()

    events = AttestationConsumer(topic).read_events()
    assert [e["event"] for e in events] == [
        "LocalTrainingEvent",
        "UpdateSubmissionEvent",
    ]
    assert all(e["group_id"] == 2 and e["server_round"] == 5 for e in events)


@needs_kafka
def test_replay_yields_the_identical_stream():
    from streaming.consumer import AttestationConsumer
    from streaming.producer import KafkaTraceLogger

    topic = _fresh_topic()
    producer = KafkaTraceLogger(topic)
    for round_number in (1, 2, 3):
        producer.log_aggregation(round_number, 3, {"total_examples": 900})
    producer.close()

    consumer = AttestationConsumer(topic)
    assert consumer.read_events() == consumer.read_events()


@needs_kafka
def test_enrichment_dispatches_into_the_event_logger():
    """The consumer turns facts into FLEventLogger calls, 1:1."""
    from streaming.consumer import AttestationConsumer
    from streaming.producer import KafkaTraceLogger

    class RecordingLogger:
        def __init__(self):
            self.calls = []

        def log_local_training(self, group_id, server_round, metrics):
            self.calls.append(("local", group_id, server_round))

        def log_update_submission(self, group_id, server_round, num_examples):
            self.calls.append(("submit", group_id, server_round))

        def log_aggregation(self, server_round, num_clients, metrics):
            self.calls.append(("aggregate", server_round, num_clients))

        def log_deployment(self, model_version, metrics):
            self.calls.append(("deploy", model_version))

    topic = _fresh_topic()
    producer = KafkaTraceLogger(topic)
    producer.log_client_round(0, 1, {"loss": 0.4, "epochs": 3}, 400)
    producer.log_aggregation(1, 3, {"total_examples": 1200})
    producer.log_deployment("v-test", {"auc": 0.7, "accuracy": 0.7})
    producer.close()

    sink = RecordingLogger()
    dispatched = AttestationConsumer(topic).enrich_into(sink)

    assert dispatched == {
        "LocalTrainingEvent": 1,
        "UpdateSubmissionEvent": 1,
        "AggregationEvent": 1,
        "DeploymentEvent": 1,
    }
    assert sink.calls == [
        ("local", 0, 1),
        ("submit", 0, 1),
        ("aggregate", 1, 3),
        ("deploy", "v-test"),
    ]
