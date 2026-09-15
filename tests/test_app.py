from unittest.mock import Mock, patch

from pytest import raises
from werkzeug.test import EnvironBuilder

from resultsdb import setup_messaging


def test_proxy_fix_extracts_single_host(app):
    """Regression test for https://github.com/release-engineering/resultsdb/issues/366"""
    builder = EnvironBuilder(method="GET", path="/api/v2.0/")
    env = builder.get_environ()
    env["HTTP_X_FORWARDED_HOST"] = "resultsdb.example.com, resultsdb.example.com"

    responses = []
    app.wsgi_app(env, lambda status, headers: responses.append(status))

    assert responses == ["300 MULTIPLE CHOICES"]
    assert env["HTTP_HOST"] == "resultsdb.example.com"


def test_app_messaging(app):
    assert app.messaging_plugin is not None
    assert type(app.messaging_plugin).__name__ == "DummyPlugin"


def test_app_messaging_none():
    app = Mock()
    app.config = {"MESSAGE_BUS_PUBLISH": False}
    setup_messaging(app)
    app.logger.info.assert_called_once_with("No messaging plugin selected")


def test_app_messaging_stomp():
    app = Mock()
    app.config = {
        "MESSAGE_BUS_PUBLISH": True,
        "MESSAGE_BUS_PLUGIN": "stomp",
        "MESSAGE_BUS_KWARGS": {
            "destination": "results.new",
            "connection": {
                "host_and_ports": [("localhost", 1234)],
            },
        },
    }
    setup_messaging(app)
    app.logger.info.assert_called_once_with("Using messaging plugin %s", "stomp")


def test_app_messaging_stomp_bad():
    app = Mock()
    app.config = {
        "MESSAGE_BUS_PUBLISH": True,
        "MESSAGE_BUS_PLUGIN": "stomp",
        "MESSAGE_BUS_KWARGS": {
            "connection": {
                "host_and_ports": [("localhost", 1234)],
            },
        },
    }
    expected_error = "Missing 'destination' option for STOMP messaging plugin"
    with raises(ValueError, match=expected_error):
        setup_messaging(app)


def test_app_messaging_kafka(monkeypatch):
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_USERNAME", "alice")
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_PASSWORD", "secret")
    app = Mock()
    app.config = {
        "MESSAGE_BUS_PUBLISH": True,
        "MESSAGE_BUS_PLUGIN": "kafka",
        "KAFKA": {
            "topic": "eng.resultsdb.result.new",
            "producer": {
                "bootstrap.servers": "localhost:9092",
            },
        },
        "MESSAGE_BUS_KWARGS": {},
    }
    with patch("resultsdb.messaging.Producer"):
        setup_messaging(app)
    app.logger.info.assert_called_once_with("Using messaging plugin %s", "kafka")
    assert type(app.messaging_plugin).__name__ == "KafkaPlugin"


def test_app_messaging_kafka_bad(monkeypatch):
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_USERNAME", "alice")
    monkeypatch.setenv("RESULTSDB_KAFKA_SASL_PASSWORD", "secret")
    app = Mock()
    app.config = {
        "MESSAGE_BUS_PUBLISH": True,
        "MESSAGE_BUS_PLUGIN": "kafka",
        "KAFKA": {
            "producer": {
                "bootstrap.servers": "localhost:9092",
            },
        },
    }
    with raises(RuntimeError, match="Invalid KAFKA configuration"):
        setup_messaging(app)
