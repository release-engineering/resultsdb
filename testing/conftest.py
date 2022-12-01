import os
from unittest.mock import patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def mock_db(tmpdir_factory):
    postgres_port = os.getenv("POSTGRES_5432_TCP", None)
    if postgres_port:
        dburi = "postgresql+psycopg2://resultsdb:resultsdb@" f"localhost:{postgres_port}/resultsdb"
    else:
        dbfile = tmpdir_factory.mktemp("data").join("test_db.sqlite")
        dburi = f"sqlite:///{dbfile}"

    with patch.dict(
        "resultsdb.app.config",
        {
            "SQLALCHEMY_DATABASE_URI": dburi,
            "MESSAGE_BUS_PUBLISH": True,
            "MESSAGE_BUS_PLUGIN": "dummy",
        },
    ):
        import resultsdb

        resultsdb.db.drop_all()
        resultsdb.db.create_all()
        yield


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
