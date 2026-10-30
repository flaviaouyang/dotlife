import doctest

from dotlife import (
    config,
    periods,
    reflections,
    schema,
    staging,
    summaries,
    validate,
)
from dotlife.dashboard import display


def load_tests(loader, tests, ignore):
    """Run the docstring examples as tests, so they can't go stale."""
    for module in (
        config,
        display,
        periods,
        reflections,
        schema,
        staging,
        summaries,
        validate,
    ):
        tests.addTests(doctest.DocTestSuite(module))
    return tests
