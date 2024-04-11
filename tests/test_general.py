import datetime
import ssl
from unittest.mock import patch

import stomp
from pytest import fixture, raises

import resultsdb.controllers.api_v2 as apiv2
import resultsdb.messaging as messaging
from resultsdb.parsers.api_v2 import parse_since

MESSAGE_BUS_KWARGS = {
    "destination": "results.new",
    "connection": {
        "host_and_ports": [("localhost", 1234)],
        "use_ssl": True,
        "ssl_version": ssl.PROTOCOL_TLSv1_2,
        "ssl_key_file": "/etc/secret/umb-client.key",
        "ssl_cert_file": "/etc/secret/umb-client.crt",
        "ssl_ca_certs": "/etc/secret/ca.pem",
    },
}


@fixture
def mock_stomp():
    with patch("resultsdb.messaging.StompPlugin._publish_with_retry.retry.sleep"):
        with patch("resultsdb.messaging.stomp.connect.StompConnection11") as mock:
            mock().is_connected.return_value = False
            yield mock


class MyRequest:
    def __init__(self, url):
        self.url = url


class TestPrevNextURL:
    def setup_method(self, method):
        self.rq = MyRequest(url="")

    def test_no_data_no_page_in_url(self, monkeypatch):
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls([], 1)
        assert data == []
        assert prev is None
        assert next is None

    def test_no_data_page_in_url(self, monkeypatch):
        self.rq.url = "?page=0"
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls([], 1)
        assert data == []
        assert prev is None
        assert next is None

    def test_data_no_page_in_url(self, monkeypatch):
        self.rq.url = "URL"
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls(list(range(10)), 1)
        assert data == [0]
        assert prev is None
        assert next == "URL?page=1"

    def test_data_no_page_in_url_stuff_in_url(self, monkeypatch):
        self.rq.url = "URL?stuff=some"
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls(list(range(10)), 1)
        assert data == [0]
        assert prev is None
        assert next == "URL?stuff=some&page=1"

    def test_data_page_and_limit_in_url(self, monkeypatch):
        self.rq.url = "URL?page=1&limit=1"
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls(list(range(10)), 1)
        assert data == [0]
        assert prev == "URL?page=0&limit=1"
        assert next == "URL?page=2&limit=1"

        self.rq.url = "URL?limit=1&page=1"
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls(list(range(10)), 1)
        assert data == [0]
        assert prev == "URL?limit=1&page=0"
        assert next == "URL?limit=1&page=2"

        self.rq.url = "URL&page=1&limit=1"
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls(list(range(10)), 1)
        assert data == [0]
        assert prev == "URL&page=0&limit=1"
        assert next == "URL&page=2&limit=1"

        self.rq.url = "URL&limit=1&page=1"
        monkeypatch.setattr(apiv2, "request", self.rq)

        data, prev, next = apiv2.prev_next_urls(list(range(10)), 1)
        assert data == [0]
        assert prev == "URL&limit=1&page=0"
        assert next == "URL&limit=1&page=2"


class TestParseSince:
    def setup_method(self, method):
        self.date_str = "2016-01-01T01:02:03.04"
        self.date_obj = datetime.datetime.strptime(
            self.date_str, "%Y-%m-%dT%H:%M:%S.%f"
        )

    def test_parse_start(self):
        start, end = parse_since(self.date_str)
        assert start == self.date_obj
        assert end is None

    def test_parse_start_with_timezone_info(self):
        start, end = parse_since(self.date_str + "Z")
        assert start == self.date_obj
        assert end is None

        start, end = parse_since(self.date_str + "+01")
        assert start == self.date_obj
        assert end is None

    def test_parse_end(self):
        start, end = parse_since(self.date_str + "," + self.date_str)
        assert start == self.date_obj
        assert end == self.date_obj


class TestMessaging:
    def test_load_plugin(self):
        plugin = messaging.load_messaging_plugin("dummy", {})
        assert isinstance(plugin, messaging.DummyPlugin)
        try:
            plugin = messaging.load_messaging_plugin("fedmsg", {})
        except KeyError as err:
            if "not found" in str(err):
                print(
                    """=============== HINT ===============
This exception can be caused by the fact, that you did not run
`python setup.py develop` before executing the testsuite.

The messaging plugins are defined as setuptools entry-points, and those live in the
.egg-info directory. If you're developing locally, that directory is usually present
in pwd due to `python setup.py develop`.

If you ran `python setup.py develop` and are still seeing this error, then:
 - you might me missing the 'fedmsg' entrypoint in setup.py
 - there can be an error in the plugin loading code"""
                )
            raise
        assert isinstance(plugin, messaging.FedmsgPlugin), (
            "check whether `fedmsg` entrypoint in setup.py points to"
            " resultsdb.messaging:FedmsgPlugin"
        )

    def test_stomp_load(self):
        message_bus_kwargs = {
            "destination": "results.new",
            "connection": {
                "host_and_ports": [("localhost", 1234)],
            },
        }
        plugin = messaging.load_messaging_plugin("stomp", message_bus_kwargs)
        assert isinstance(plugin, messaging.StompPlugin)
        assert plugin.destination == "results.new"

    def test_stomp_missing_destination(self):
        message_bus_kwargs = {
            "connection": {
                "host_and_ports": [("localhost", 1234)],
            },
        }
        expected_error = "Missing 'destination' option for STOMP messaging plugin"
        with raises(ValueError, match=expected_error):
            messaging.load_messaging_plugin("stomp", message_bus_kwargs)

    def test_stomp_ssl(self):
        # Run twice to ensure that the original configuration is not modified.
        for _ in (1, 2):
            plugin = messaging.load_messaging_plugin("stomp", MESSAGE_BUS_KWARGS)
            assert plugin.connection == {
                "host_and_ports": [("localhost", 1234)],
            }
            assert plugin.use_ssl is True
            assert plugin.ssl_args == {
                "for_hosts": [("localhost", 1234)],
                "key_file": "/etc/secret/umb-client.key",
                "cert_file": "/etc/secret/umb-client.crt",
                "ca_certs": "/etc/secret/ca.pem",
                "ssl_version": ssl.PROTOCOL_TLSv1_2,
            }

    def test_stomp_publish(self, mock_stomp):
        plugin = messaging.load_messaging_plugin("stomp", MESSAGE_BUS_KWARGS)
        assert mock_stomp().is_connected() is False
        plugin.publish({})
        mock_stomp().connect.assert_called_once()
        mock_stomp().send.assert_called_once()

    def test_stomp_publish_connect_failed(self, mock_stomp):
        plugin = messaging.load_messaging_plugin("stomp", MESSAGE_BUS_KWARGS)

        mock_stomp().connect.side_effect = stomp.exception.ConnectFailedException()
        with raises(stomp.exception.ConnectFailedException):
            plugin.publish({})

        assert mock_stomp().connect.call_count == 3
        mock_stomp().send.assert_not_called()

    def test_stomp_publish_send_failed(self, mock_stomp):
        plugin = messaging.load_messaging_plugin("stomp", MESSAGE_BUS_KWARGS)

        mock_stomp().send.side_effect = stomp.exception.StompException()
        with raises(stomp.exception.StompException):
            plugin.publish({})

        assert mock_stomp().connect.call_count == 3
        assert mock_stomp().send.call_count == 3


class TestGetResultsParseArgs:
    # TODO: write something!
    pass
