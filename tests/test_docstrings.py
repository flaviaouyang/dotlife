import doctest

from dotlife import periods, schema


def load_tests(loader, tests, ignore):
    """Run the docstring examples as tests, so they can't go stale."""
    for module in (periods, schema):
        tests.addTests(doctest.DocTestSuite(module))
    return tests
