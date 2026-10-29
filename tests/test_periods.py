import unittest
from datetime import date, time
from statistics import mean

from dotlife.periods import (
    Period,
    clock_from_minutes,
    minutes_after_evening,
    period_end,
    period_start,
)


class PeriodStartTest(unittest.TestCase):
    """Weeks start on Monday; months on the first."""

    def test_week_starts_on_monday(self):
        """Every day of a week maps to its Monday, including Sunday."""
        for day in range(9, 16):
            self.assertEqual(
                period_start(date(2026, 3, day), Period.WEEK), date(2026, 3, 9)
            )

    def test_week_spanning_new_year(self):
        """A week that spans the new year starts in the old year."""
        self.assertEqual(
            period_start(date(2027, 1, 1), Period.WEEK), date(2026, 12, 28)
        )

    def test_month(self):
        """A month starts on its first day."""
        self.assertEqual(
            period_start(date(2026, 2, 28), Period.MONTH), date(2026, 2, 1)
        )


class PeriodEndTest(unittest.TestCase):
    """The end is the first day of the next period."""

    def test_week(self):
        """A week ends seven days after its Monday, across a month boundary."""
        self.assertEqual(period_end(date(2026, 3, 30), Period.WEEK), date(2026, 4, 6))

    def test_months_of_every_length(self):
        """Months of 28, 29, 30 and 31 days, and December, end on the next first."""
        cases = {
            date(2026, 2, 1): date(2026, 3, 1),
            date(2028, 2, 1): date(2028, 3, 1),
            date(2026, 4, 1): date(2026, 5, 1),
            date(2026, 1, 1): date(2026, 2, 1),
            date(2026, 12, 1): date(2027, 1, 1),
        }
        for start, end in cases.items():
            with self.subTest(start=start):
                self.assertEqual(period_end(start, Period.MONTH), end)


class ClockMathsTest(unittest.TestCase):
    """Clock times measured from 18:00 average correctly across midnight."""

    def test_minutes_after_evening(self):
        """Evening times come first and the day wraps at 18:00."""
        cases = {time(18): 0, time(23, 30): 330, time(1, 15): 435, time(17, 59): 1439}
        for clock, minutes in cases.items():
            with self.subTest(clock=clock):
                self.assertEqual(minutes_after_evening(clock), minutes)

    def test_round_trip(self):
        """Every minute of the day converts there and back unchanged."""
        for minutes in range(1440):
            self.assertEqual(
                minutes_after_evening(clock_from_minutes(minutes)), minutes
            )

    def test_mean_bedtime_across_midnight(self):
        """The mean of 23:30 and 00:30 is midnight, not noon."""
        bedtimes = [time(23, 30), time(0, 30)]
        self.assertEqual(
            clock_from_minutes(mean(map(minutes_after_evening, bedtimes))), time(0)
        )


if __name__ == "__main__":
    unittest.main()
