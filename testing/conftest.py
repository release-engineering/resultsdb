import os
from unittest.mock import patch

import pytest

from resultsdb import create_app
from resultsdb.models import db


@pytest.fixture(scope="session", autouse=True)
def mock_oidc():
    with patch("resultsdb.OIDCAuthentication") as oidc:
        oidc().token_auth.side_effect = lambda _provider: lambda fn: fn
        oidc().oidc_auth.side_effect = lambda _provider: lambda fn: fn
        oidc().oidc_logout.side_effect = lambda _provider: lambda fn: fn
        oidc().current_token_identity = {"uid": "testuser1"}
        yield


@pytest.fixture(scope="session", autouse=True)
def app(mock_oidc):
    app = create_app("resultsdb.config.TestingConfig")
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app


def pytest_addoption(parser):
    """
    Add an option to the py.test parser to detect when the functional tests
    should be detected and run
    """

    parser.addoption(
        "-F", "--functional", action="store_true", default=False, help="Add functional tests"
    )


def pytest_ignore_collect(path, config):
    """Prevents collection of any files named functest* to speed up non
    integration tests"""
    if path.fnmatch("*functest*"):
        try:
            is_functional = config.getvalue("functional")
        except KeyError:
            return True

        return not is_functional


def pytest_configure(config):
    """Called after command line options have been parsed and all plugins and
    initial conftest files been loaded."""

    os.environ["TEST"] = "true"
