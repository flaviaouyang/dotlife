import doctest

from dotlife import config, journal, periods, schema, summaries, validate


def load_tests(loader, tests, ignore):
    """Run the docstring examples as tests, so they can't go stale."""
    for module in (config, journal, periods, schema, summaries, validate):
        tests.addTests(doctest.DocTestSuite(module))
    return tests
