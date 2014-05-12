def pytest_addoption(parser):
    """
    Add an option to the py.test parser to detect when the functional tests
    should be detected and run
    """

    parser.addoption('-F', '--functional', action='store_true', default=False,
                     help='Add functional tests')


def pytest_ignore_collect(path, config):
    """Prevents collection of any files named functest* to speed up non
        integration tests"""
    if path.fnmatch('*functest*'):
        try:
            is_functional = config.getvalue('functional')
        except KeyError:
            return True

        return not is_functional


def pytest_configure(config):
    """Called after command line options have been parsed and all plugins and
    initial conftest files been loaded."""

    pass
