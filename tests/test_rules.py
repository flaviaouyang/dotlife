import unittest
from zoneinfo import ZoneInfo

from dotlife.categories import SLEEP, WORKOUTS
from dotlife.rules import (
    date_is_start_date,
    date_is_wake_date,
    end_after_start,
    watch_worn,
)
from dotlife.schema import Context, row_parser

NEW_YORK = Context(
    timezone=ZoneInfo("America/New_York"),
    options={"watch_off_steps": 1000, "watch_off_sedentary_min": 480},
)


def sleep_row(day: str, start: str, end: str) -> dict:
    """Parse a sleep row from its date and timestamps.

    Args:
        day: The ``date`` cell.
        start: The ``start`` cell.
        end: The ``end`` cell.

    Returns:
        The parsed row.
    """
    return row_parser(SLEEP)(
        {"date": day, "start": start, "end": end, "source": "watch"}
    )


class WakeDateTest(unittest.TestCase):
    """A night counts toward the local date its sleeper woke up."""

    def test_night_across_dst_change(self):
        """A night spanning the US spring-forward change files under the wake date."""
        row = sleep_row(
            "2026-03-08", "2026-03-07T23:30-05:00", "2026-03-08T07:30-04:00"
        )
        self.assertIsNone(date_is_wake_date(row, NEW_YORK))

    def test_bedtime_date_is_wrong(self):
        """Filing a night under the day it started is reported."""
        row = sleep_row(
            "2026-03-07", "2026-03-07T23:30-05:00", "2026-03-08T07:30-04:00"
        )
        self.assertIn("wake date 2026-03-08", date_is_wake_date(row, NEW_YORK) or "")

    def test_offset_other_than_local(self):
        """Timestamps written in UTC are converted to local time first."""
        row = sleep_row(
            "2026-03-07", "2026-03-07T20:00+00:00", "2026-03-08T03:30+00:00"
        )
        self.assertIsNone(date_is_wake_date(row, NEW_YORK))

    def test_end_before_start(self):
        """A session that ends before it starts is reported."""
        row = sleep_row(
            "2026-03-08", "2026-03-08T07:30-04:00", "2026-03-07T23:30-05:00"
        )
        self.assertIsNotNone(end_after_start(row, NEW_YORK))


class StartDateTest(unittest.TestCase):
    """A workout counts toward the local date it started."""

    def test_late_workout_crossing_midnight(self):
        """A session from 23:30 to 00:30 files under the day it started."""
        parse = row_parser(WORKOUTS)
        raw = {
            "start": "2026-06-01T23:30-04:00",
            "end": "2026-06-02T00:30-04:00",
            "type": "run",
            "source": "watch",
        }
        self.assertIsNone(
            date_is_start_date(parse({**raw, "date": "2026-06-01"}), NEW_YORK)
        )
        self.assertIsNotNone(
            date_is_start_date(parse({**raw, "date": "2026-06-02"}), NEW_YORK)
        )


class WatchWornTest(unittest.TestCase):
    """Days with few steps and little sedentary time count as watch off."""

    def test_cases(self):
        """Enough steps, enough or no sedentary time means worn; no steps never is."""
        cases = [
            (5000, 600, True),
            (300, 600, True),
            (1000, 0, True),
            (300, 100, False),
            (300, None, True),
            (None, 900, False),
        ]
        for steps, sedentary, worn in cases:
            with self.subTest(steps=steps, sedentary=sedentary):
                row = {"steps": steps, "sedentary_min": sedentary}
                self.assertIs(watch_worn(row, NEW_YORK), worn)

    def test_fallback_source(self):
        """A fallback device's day is left out, however many steps it has."""
        context = Context(
            NEW_YORK.timezone, {**NEW_YORK.options, "fallback_sources": ["iphone"]}
        )
        row = {"steps": 5252, "sedentary_min": None, "source": "iphone"}
        self.assertFalse(watch_worn(row, context))
        self.assertTrue(watch_worn(row | {"source": "apple-watch"}, context))
        self.assertTrue(watch_worn(row, NEW_YORK))


class ContextTest(unittest.TestCase):
    """Categories are on unless config switches them off."""

    def test_enabled_by_default(self):
        """A missing ``enabled`` key means on; ``false`` means off."""
        zone = ZoneInfo("UTC")
        self.assertIs(Context(zone, {}).enabled, True)
        self.assertIs(Context(zone, {"enabled": False}).enabled, False)


if __name__ == "__main__":
    unittest.main()
