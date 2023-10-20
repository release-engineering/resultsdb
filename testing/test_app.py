from unittest.mock import Mock

from pytest import raises

from resultsdb import setup_messaging


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
