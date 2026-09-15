import json
from unittest.mock import Mock, patch

from confluent_kafka import KafkaError, KafkaException
from pytest import fixture, raises

from resultsdb.messaging import KafkaPlugin


@fixture
def kafka_plugin_args(monkeypatch):
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_USERNAME", "alice")
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_PASSWORD", "secret")
    return {
        "topic": "eng.resultsdb.result.new",
        "producer": {
            "bootstrap.servers": "localhost:9092",
            "client.id": "resultsdb-test",
            "retries": 3,
        },
        "flush_timeout_seconds": 15.0,
    }


@fixture
def kafka_plugin(kafka_plugin_args):
    with patch("resultsdb.messaging.Producer") as mock_producer_class:
        mock_producer = Mock()
        mock_producer.flush.return_value = 0
        mock_producer_class.return_value = mock_producer
        plugin = KafkaPlugin(**kafka_plugin_args)
        yield plugin, mock_producer


def _simulate_successful_produce(mock_producer):
    """Make produce() invoke the on_delivery callback with no error on flush()."""
    callbacks = []

    def capture_produce(topic, value=None, on_delivery=None):
        callbacks.append(on_delivery)

    def trigger_flush(timeout=None):
        for cb in callbacks:
            if cb:
                cb(None, Mock())
        callbacks.clear()
        return 0

    mock_producer.produce.side_effect = capture_produce
    mock_producer.flush.side_effect = trigger_flush


def _simulate_failed_produce(mock_producer, error):
    """Make produce() invoke the on_delivery callback with an error on flush()."""
    callbacks = []

    def capture_produce(topic, value=None, on_delivery=None):
        callbacks.append(on_delivery)

    def trigger_flush(timeout=None):
        for cb in callbacks:
            if cb:
                cb(error, None)
        callbacks.clear()
        return 0

    mock_producer.produce.side_effect = capture_produce
    mock_producer.flush.side_effect = trigger_flush


def test_publish_success(kafka_plugin):
    plugin, mock_producer = kafka_plugin
    _simulate_successful_produce(mock_producer)

    plugin.publish({"id": 1, "outcome": "PASSED"})

    mock_producer.produce.assert_called_once()
    args, kwargs = mock_producer.produce.call_args
    assert args[0] == "eng.resultsdb.result.new"
    payload = json.loads(kwargs["value"])
    assert payload["id"] == 1
    assert payload["outcome"] == "PASSED"
    mock_producer.flush.assert_called_once_with(timeout=15.0)


def test_publish_delivery_error(kafka_plugin):
    plugin, mock_producer = kafka_plugin
    mock_error = Mock()
    mock_error.__str__ = Mock(return_value="Connection failed")
    _simulate_failed_produce(mock_producer, mock_error)

    with raises(KafkaException):
        plugin.publish({"id": 1})


def test_publish_flush_timeout(kafka_plugin):
    plugin, mock_producer = kafka_plugin
    mock_producer.flush.return_value = 1

    with raises(KafkaException) as exc_info:
        plugin.publish({"id": 1})

    err = exc_info.value.args[0]
    assert isinstance(err, KafkaError)
    assert err.code() == KafkaError._MSG_TIMED_OUT


def test_kafka_plugin_creation(kafka_plugin_args):
    with patch("resultsdb.messaging.Producer") as mock_producer_class:
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer

        plugin = KafkaPlugin(**kafka_plugin_args)

        mock_producer_class.assert_called_once_with(
            {
                "bootstrap.servers": "localhost:9092",
                "client.id": "resultsdb-test",
                "retries": 3,
                "sasl.username": "alice",
                "sasl.password": "secret",
            }
        )
        assert plugin._config.topic == "eng.resultsdb.result.new"
        assert plugin._producer is mock_producer


def test_kafka_plugin_missing_sasl(kafka_plugin_args, monkeypatch):
    monkeypatch.delenv("RESULTSDB_KAFKA_SASL_USERNAME", raising=False)
    monkeypatch.delenv("RESULTSDB_KAFKA_SASL_PASSWORD", raising=False)
    with raises(RuntimeError, match="RESULTSDB_KAFKA_SASL_USERNAME"):
        KafkaPlugin(**kafka_plugin_args)


def test_kafka_plugin_invalid_config(monkeypatch):
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_USERNAME", "alice")
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_PASSWORD", "secret")
    with raises(RuntimeError, match="Invalid KAFKA configuration"):
        KafkaPlugin(producer={"bootstrap.servers": "localhost:9092"})
