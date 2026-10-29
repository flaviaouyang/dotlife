import unittest
from datetime import date
from pathlib import Path

from dotlife.categories import ACTIVITY
from dotlife.config import find_data
from dotlife.load import load_dataset
from dotlife.periods import Period
from dotlife.summaries import daily_values, period_values

ROOT = Path(__file__).resolve().parent.parent


class SampleDatasetTest(unittest.TestCase):
    """The sample loads completely, and its numbers match what the mockup shows."""

    @classmethod
    def setUpClass(cls):
        """Load the sample once."""
        cls.dataset = load_dataset(find_data(ROOT / "config.toml", ROOT / "sample"))

    def test_everything_loads(self):
        """All 28 categories, every activity row, and the reflections."""
        self.assertEqual(len(self.dataset.categories), 28)
        self.assertEqual(len(self.dataset.rows["activity"]), 179)
        self.assertEqual(len(self.dataset.reflections), 159)
        self.assertEqual(self.dataset.as_of, date(2026, 8, 30))

    def test_weekly_steps(self):
        """Average steps for 24 to 30 Aug, leaving out watch-off days: 9,661."""
        daily = daily_values(
            ACTIVITY,
            self.dataset.rows["activity"],
            "steps",
            self.dataset.contexts["activity"],
        )
        week = period_values(daily, ACTIVITY.metrics[0].aggregate, Period.WEEK)
        self.assertAlmostEqual(week[date(2026, 8, 24)], 9661.43, places=2)
        self.assertNotIn(date(2026, 5, 14), daily)


if __name__ == "__main__":
    unittest.main()
