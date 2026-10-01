import io
from unittest.mock import patch

import requests
import urllib3
from pytest import raises
from urllib3.exceptions import ProtocolError
from urllib3.response import HTTPResponse

from resultsdb import oidc_requests_session


def _flaky_then_ok(fail_times):
    """Build a `_make_request` replacement that raises a connection reset
    `fail_times` times, then returns a fake 200 response. Never touches the
    network: `HTTPConnectionPool._make_request` is the point urllib3 would
    otherwise open the real socket at."""
    attempts = []

    def _make_request(self, conn, method, url, *args, **kwargs):
        attempts.append((method, url))
        if len(attempts) <= fail_times:
            raise ProtocolError(
                "Connection aborted.",
                ConnectionResetError(104, "Connection reset by peer"),
            )
        return HTTPResponse(body=io.BytesIO(b""), status=200, preload_content=False)

    return attempts, _make_request


def test_oidc_requests_session_retries_on_connection_reset():
    """Regression test for RHELWF-14685: a single reset connection to the
    OIDC provider (e.g. during token introspection) used to fail the whole
    resultsdb request outright. The retrying session should absorb it."""
    session = oidc_requests_session()
    attempts, flaky_make_request = _flaky_then_ok(fail_times=2)

    with patch.object(
        urllib3.connectionpool.HTTPConnectionPool, "_make_request", flaky_make_request
    ):
        response = session.post(
            "https://auth.example.invalid/introspect", data={"token": "x"}
        )

    assert response.status_code == 200
    assert len(attempts) == 3


def test_plain_session_fails_on_connection_reset():
    """Baseline: without the retrying session (what resultsdb used before
    the fix), the same reset fails the request on the first attempt."""
    session = requests.Session()
    attempts, flaky_make_request = _flaky_then_ok(fail_times=2)

    with patch.object(
        urllib3.connectionpool.HTTPConnectionPool, "_make_request", flaky_make_request
    ):
        with raises(requests.exceptions.ConnectionError):
            session.post("https://auth.example.invalid/introspect", data={"token": "x"})

    assert len(attempts) == 1
