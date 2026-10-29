import math
import unittest
from datetime import date, datetime, timedelta, timezone

from dotlife.categories import ACTIVITY, CATEGORIES, MOOD, SLEEP
from dotlife.schema import row_parser


class CategorySpecTest(unittest.TestCase):
    """Every built-in spec is internally consistent."""

    def test_names_and_files_are_unique(self):
        """No two categories share a name or a file."""
        for attribute in ("name", "file"):
            values = [getattr(category, attribute) for category in CATEGORIES]
            self.assertEqual(len(values), len(set(values)), attribute)

    def test_key_columns_exist(self):
        """Each key column is one of the category's columns."""
        for category in CATEGORIES:
            with self.subTest(category=category.name):
                self.assertLessEqual(set(category.key), set(category.columns))

    def test_metric_columns_are_unique_within_a_category(self):
        """No category repeats a column."""
        for category in CATEGORIES:
            with self.subTest(category=category.name):
                self.assertEqual(len(category.columns), len(set(category.columns)))

    def test_limits_and_plausible_bounds_are_ordered(self):
        """Hard limits and plausible bounds run low to high, bounds inside limits."""
        for category in CATEGORIES:
            for metric in category.metrics:
                with self.subTest(metric=f"{category.name}.{metric.column}"):
                    low = -math.inf if metric.minimum is None else metric.minimum
                    high = math.inf if metric.maximum is None else metric.maximum
                    self.assertLess(low, high)
                    if metric.plausible is not None:
                        self.assertLess(metric.plausible[0], metric.plausible[1])
                        self.assertLessEqual(low, metric.plausible[0])
                        self.assertLessEqual(metric.plausible[1], high)

    def test_related_metrics_exist(self):
        """Every related metric names a real category and column."""
        columns = {
            f"{category.name}.{metric.column}"
            for category in CATEGORIES
            for metric in category.metrics
        }
        for category in CATEGORIES:
            for metric in category.metrics:
                with self.subTest(metric=metric.column):
                    self.assertLessEqual(set(metric.related), columns)

    def test_columns_in_file_order(self):
        """Fields come first, then metrics."""
        self.assertEqual(MOOD.columns, ("date", "source", "mood", "energy", "stress"))


class RowParserTest(unittest.TestCase):
    """Rows parse to typed values; problems name their column."""

    def test_parses_types(self):
        """Dates, timestamps, text and numbers each get their own type."""
        row = row_parser(SLEEP)(
            {
                "date": "2026-03-08",
                "start": "2026-03-07T23:40+01:00",
                "end": "2026-03-08T07:10+01:00",
                "source": "watch",
                "asleep_min": "412",
            }
        )
        offset = timezone(timedelta(hours=1))
        self.assertEqual(
            row,
            {
                "date": date(2026, 3, 8),
                "start": datetime(2026, 3, 7, 23, 40, tzinfo=offset),
                "end": datetime(2026, 3, 8, 7, 10, tzinfo=offset),
                "source": "watch",
                "asleep_min": 412.0,
                "deep_min": None,
                "rem_min": None,
                "light_min": None,
                "awake_min": None,
            },
        )

    def test_empty_metric_is_missing(self):
        """An empty or absent metric cell becomes None, never zero."""
        row = row_parser(ACTIVITY)(
            {"date": "2026-01-05", "source": "phone", "steps": " "}
        )
        self.assertIsNone(row["steps"])
        self.assertIsNone(row["floors"])

    def test_errors_name_the_column(self):
        """Each kind of bad cell raises ValueError starting with its column."""
        base = {"date": "2026-01-05", "source": "manual"}
        cases = {
            "required": ({"date": "2026-01-05"}, "source"),
            "bad date": ({**base, "date": "05/01/2026"}, "date"),
            "bad number": ({**base, "mood": "great"}, "mood"),
            "not finite": ({**base, "mood": "nan"}, "mood"),
        }
        parse = row_parser(MOOD)
        for case, (raw, column) in cases.items():
            with (
                self.subTest(case=case),
                self.assertRaisesRegex(ValueError, f"^{column}: "),
            ):
                parse(raw)

    def test_timestamp_needs_offset(self):
        """A timestamp without a UTC offset is ambiguous around DST, so it fails."""
        raw = {
            "date": "2026-03-08",
            "start": "2026-03-07T23:40",
            "end": "2026-03-08T07:10+01:00",
            "source": "watch",
        }
        with self.assertRaisesRegex(ValueError, "^start: .*no UTC offset"):
            row_parser(SLEEP)(raw)


if __name__ == "__main__":
    unittest.main()
