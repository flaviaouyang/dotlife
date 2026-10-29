import doctest

from dotlife import config, periods, schema


def load_tests(loader, tests, ignore):
    """Run the docstring examples as tests, so they can't go stale."""
    for module in (config, periods, schema):
        tests.addTests(doctest.DocTestSuite(module))
    return tests
