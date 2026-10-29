import unittest
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from dotlife.categories import ACTIVITY, SLEEP
from dotlife.periods import Period
from dotlife.schema import Aggregate, Context, row_parser
from dotlife.summaries import (
    Assessment,
    Status,
    Tone,
    UsualRange,
    assess,
    clock_by_day,
    cycle_status,
    daily_counts,
    daily_values,
    display_value,
    flow_by_day,
    notable,
    period_values,
    stuck_against,
    usual_range,
)

LONDON = ZoneInfo("Europe/London")
CONTEXT = Context(LONDON, {"watch_off_steps": 1000, "watch_off_sedentary_min": 480})


def sleep_rows(*sessions: tuple[str, str, str, str]) -> list[dict]:
    """Parse sleep rows.

    Args:
        *sessions: (date, start, end, asleep_min) per session.

    Returns:
        Parsed rows.
    """
    parse = row_parser(SLEEP)
    return [
        parse(
            {
                "date": day,
                "start": start,
                "end": end,
                "source": "watch",
                "asleep_min": asleep,
            }
        )
        for day, start, end, asleep in sessions
    ]


class DailyValuesTest(unittest.TestCase):
    """Daily values add up sessions and skip watch-off days and missing values."""

    def test_sessions_on_one_date_add_up(self):
        """A night and a nap filed under the same date count together."""
        rows = sleep_rows(
            ("2026-03-08", "2026-03-07T23:30+00:00", "2026-03-08T06:30+00:00", "400"),
            ("2026-03-08", "2026-03-08T14:00+00:00", "2026-03-08T14:40+00:00", "35"),
        )
        self.assertEqual(
            daily_values(SLEEP, rows, "asleep_min", CONTEXT), {date(2026, 3, 8): 435.0}
        )

    def test_watch_off_and_missing_are_left_out(self):
        """A watch-off day and an empty cell add nothing, not zero."""
        parse = row_parser(ACTIVITY)
        rows = [
            parse(
                {
                    "date": "2026-03-02",
                    "source": "watch",
                    "steps": "8000",
                    "sedentary_min": "600",
                }
            ),
            parse(
                {
                    "date": "2026-03-03",
                    "source": "watch",
                    "steps": "200",
                    "sedentary_min": "100",
                }
            ),
            parse(
                {
                    "date": "2026-03-04",
                    "source": "watch",
                    "steps": "",
                    "sedentary_min": "600",
                }
            ),
        ]
        self.assertEqual(
            daily_values(ACTIVITY, rows, "steps", CONTEXT), {date(2026, 3, 2): 8000.0}
        )

    def test_counts_with_a_filter(self):
        """Counting rows per date honours the row filter."""
        rows = [
            {"date": date(2026, 3, 2), "type": "run"},
            {"date": date(2026, 3, 2), "type": "yoga"},
        ]
        self.assertEqual(
            daily_counts(rows, lambda row: row["type"] == "run"),
            {date(2026, 3, 2): 1.0},
        )


class ClockTest(unittest.TestCase):
    """Bedtimes come from the longest session and cope with midnight."""

    def test_bedtime_of_main_session(self):
        """The nap is ignored; a bedtime after midnight sorts as late."""
        rows = sleep_rows(
            ("2026-06-02", "2026-06-02T00:30+01:00", "2026-06-02T07:30+01:00", "400"),
            ("2026-06-02", "2026-06-02T14:00+01:00", "2026-06-02T14:30+01:00", "25"),
        )
        self.assertEqual(clock_by_day(rows, "start", LONDON), {date(2026, 6, 2): 390.0})


class PeriodValuesTest(unittest.TestCase):
    """Each summary rule combines a period's days its own way."""

    def test_each_aggregate(self):
        """Sum, mean, last and days above zero, for one week."""
        daily = {date(2026, 3, 2): 2.0, date(2026, 3, 4): 0.0, date(2026, 3, 3): 4.0}
        expected = {
            Aggregate.SUM: 6.0,
            Aggregate.MEAN: 2.0,
            Aggregate.LAST: 0.0,
            Aggregate.DAYS: 2.0,
        }
        for aggregate, value in expected.items():
            with self.subTest(aggregate=aggregate):
                self.assertEqual(
                    period_values(daily, aggregate, Period.WEEK),
                    {date(2026, 3, 2): value},
                )

    def test_months(self):
        """Days fall into calendar months."""
        daily = {date(2026, 1, 31): 1.0, date(2026, 2, 1): 2.0}
        self.assertEqual(
            period_values(daily, Aggregate.SUM, Period.MONTH),
            {date(2026, 1, 1): 1.0, date(2026, 2, 1): 2.0},
        )


class UsualRangeTest(unittest.TestCase):
    """The usual range uses only full periods before the current one."""

    weeks = {
        date(2026, 3, 2) + timedelta(weeks=index): float(index) for index in range(10)
    }

    def test_excludes_current_and_older_periods(self):
        """Eight weeks before the current one: values 1 to 8, not 0 or 9."""
        self.assertEqual(
            usual_range(self.weeks, date(2026, 5, 4), Period.WEEK, 8),
            UsualRange(2.75, 4.5, 6.25, 8),
        )

    def test_too_little_history(self):
        """Fewer periods with data than the minimum gives no range."""
        self.assertIsNone(usual_range(self.weeks, date(2026, 3, 16), Period.WEEK, 8))


class AssessTest(unittest.TestCase):
    """Values outside the range get a tone from the metric's better direction."""

    usual = UsualRange(10.0, 12.0, 14.0, 8)

    def test_cases(self):
        """Inside is usual and neutral; outside is good or bad, or neutral."""
        cases = [
            (12.0, True, Status.USUAL, Tone.NEUTRAL, 0.0),
            (16.0, True, Status.ABOVE, Tone.GOOD, 0.5),
            (8.0, True, Status.BELOW, Tone.BAD, 0.5),
            (8.0, False, Status.BELOW, Tone.GOOD, 0.5),
            (16.0, None, Status.ABOVE, Tone.NEUTRAL, 0.5),
        ]
        for value, better, status, tone, distance in cases:
            with self.subTest(value=value, better=better):
                self.assertEqual(
                    assess(value, self.usual, better),
                    Assessment(status, tone, distance),
                )

    def test_notable_ranks_by_distance(self):
        """Neutral ones are skipped; the furthest out comes first."""
        assessments = {
            "sleep": assess(9.0, self.usual, True),
            "steps": assess(20.0, self.usual, True),
            "weight": assess(30.0, self.usual, None),
            "mood": assess(12.0, self.usual, True),
        }
        self.assertEqual(notable(assessments, 4), ["steps", "sleep"])


class StuckTest(unittest.TestCase):
    """A flat metric is stuck only while a related one leaves its usual range."""

    usual = UsualRange(10.0, 12.0, 14.0, 8)
    vo2max = {date(2026, 3, 5): 40.8, date(2026, 5, 3): 42.1}

    def test_flat_while_related_moves(self):
        """Unchanged since before the window, and resting heart rate moved."""
        related = {
            "heart.resting_hr_bpm": assess(8.0, self.usual, False),
            "activity.active_min": assess(12.0, self.usual, True),
        }
        self.assertEqual(
            stuck_against(self.vo2max, related, date(2026, 7, 6)),
            ("heart.resting_hr_bpm",),
        )

    def test_changed_recently_or_nothing_moved(self):
        """A recent change, or related metrics all usual, means not stuck."""
        moved = {"heart.resting_hr_bpm": assess(8.0, self.usual, False)}
        calm = {"heart.resting_hr_bpm": assess(12.0, self.usual, False)}
        self.assertEqual(stuck_against(self.vo2max, moved, date(2026, 4, 1)), ())
        self.assertEqual(stuck_against(self.vo2max, calm, date(2026, 7, 6)), ())


class DisplayValueTest(unittest.TestCase):
    """Only units with an alternative convert; bad settings say what's allowed."""

    def test_conversions(self):
        """Kilograms to pounds, mmol/L to mg/dL, and anything else unchanged."""
        value, unit = display_value(5.0, "mmol/L", {"glucose": "mg/dL"})
        self.assertAlmostEqual(value, 90.091)
        self.assertEqual(unit, "mg/dL")
        self.assertEqual(display_value(70.0, "kg", {}), (70.0, "kg"))
        self.assertEqual(
            display_value(8000.0, "steps", {"weight": "lb"}), (8000.0, "steps")
        )

    def test_unknown_unit(self):
        """An unsupported display unit raises a message listing the choices."""
        with self.assertRaisesRegex(ValueError, "weight must be one of kg, lb"):
            display_value(70.0, "kg", {"weight": "stone"})


if __name__ == "__main__":
    unittest.main()


class CycleTest(unittest.TestCase):
    """Period days with no recorded amount still start and extend a period."""

    def test_unrecorded_flow_counts_as_a_period_day(self):
        """An empty flow level is a period day; 0 is a day without one."""
        levels = {1: 0.0, 2: None, 3: 2.0, 4: None, 5: 0.0}
        rows = [
            {"date": date(2026, 1, day), "flow_level": level}
            for day, level in levels.items()
        ]
        status = cycle_status(flow_by_day(rows), date(2026, 1, 10))
        assert status is not None
        self.assertEqual(
            (status.last_start, status.last_end, status.day),
            (date(2026, 1, 2), date(2026, 1, 4), 9),
        )
