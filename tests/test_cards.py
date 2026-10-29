import unittest
from datetime import date
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

from dotlife.categories import ACTIVITY, BODY
from dotlife.config import Goal, find_data, goal_for, goal_problems
from dotlife.dashboard.cards import CardChart, ChartKind, Selection, build_overview
from dotlife.load import load_dataset
from dotlife.periods import Period
from dotlife.schema import Context

ROOT = Path(__file__).resolve().parent.parent


def context(options: dict) -> Context:
    """Build a context with the given options.

    Args:
        options: The category's config section.

    Returns:
        The context.
    """
    return Context(ZoneInfo("UTC"), options)


class GoalConfigTest(unittest.TestCase):
    """Goals follow the metric's direction unless they say otherwise."""

    def test_forms(self):
        """A number, at_least and at_most all parse; none means no goal."""
        steps, weight = ACTIVITY.metrics[0], BODY.metrics[0]
        self.assertEqual(
            goal_for(steps, context({"goals": {"steps": 8000}})), Goal(8000.0, True)
        )
        at_most = context({"goals": {"weight_kg": {"at_most": 70}}})
        self.assertEqual(goal_for(weight, at_most), Goal(70.0, False))
        self.assertIsNone(goal_for(steps, context({})))

    def test_mistakes(self):
        """Unknown columns, missing directions and bad values are reported."""
        bad = context({"goals": {"stepz": 1, "weight_kg": 70, "steps": "lots"}})
        problems = goal_problems(ACTIVITY, bad) + goal_problems(
            BODY, context({"goals": {"weight_kg": 70}})
        )
        self.assertEqual(len(problems), 4)
        self.assertTrue(any("at_least" in problem for problem in problems))


class SampleGoalTextTest(unittest.TestCase):
    """The sample's goals read correctly for a week and a month."""

    @classmethod
    def setUpClass(cls):
        """Load the sample once."""
        cls.dataset = load_dataset(find_data(ROOT / "config.toml", ROOT / "sample"))

    def goals(self, selection: Selection) -> dict[str, str]:
        """Return each card's goal text for a selection.

        Args:
            selection: The chosen period.

        Returns:
            Goal text by card label, for cards with a goal.
        """
        cards = build_overview(self.dataset, selection).cards
        return {card.label: card.goal for card in cards if card.goal}

    def test_week(self):
        """Daily goals count days; weekly totals compare the total."""
        goals = self.goals(Selection(Period.WEEK, date(2026, 8, 24), False))
        self.assertEqual(goals["Steps"], "Goal 10,000 steps: reached on 3 of 7 days")
        self.assertEqual(goals["Active time"], "Goal 2 h 30 m a week: reached")
        self.assertEqual(
            goals["Time asleep"], "Goal 7 h 30 m: reached on 1 of 7 nights"
        )
        self.assertEqual(
            goals["Weight"], "Goal at most 72.0 kg: reached on 3 of 4 days"
        )

    def test_month_scales_weekly_totals(self):
        """A month's total goal is the weekly goal scaled to the month's length."""
        goals = self.goals(Selection(Period.MONTH, date(2026, 7, 1), False))
        self.assertEqual(goals["Active time"], "Goal 11 h 04 m a month: reached")


class CardChartTest(unittest.TestCase):
    """Each kind of metric gets the chart that suits it."""

    def test_chart_kinds(self):
        """Averages are lines, totals bars, bedtime dots, breakdowns stacks."""
        dataset = load_dataset(find_data(ROOT / "config.toml", ROOT / "sample"))
        selection = Selection(Period.WEEK, date(2026, 8, 24), True)
        charts = {
            card.label: card.chart for card in build_overview(dataset, selection).cards
        }
        kinds = {
            label: chart.kind if chart else None for label, chart in charts.items()
        }
        self.assertEqual(kinds["Steps"], ChartKind.LINE)
        self.assertEqual(kinds["Active time"], ChartKind.BARS)
        self.assertEqual(kinds["Bedtime"], ChartKind.DOTS)
        self.assertEqual(kinds["Habit check-ins"], ChartKind.GRID)
        self.assertEqual(kinds["Time tracked"], ChartKind.STACK)
        self.assertEqual(kinds["Spending"], ChartKind.STACK)
        self.assertIsNone(kinds["VO2 max"])
        steps = cast(CardChart, charts["Steps"])
        self.assertIsNotNone(steps.usual)
        self.assertEqual(steps.goals[-1], (date(2026, 8, 24), 10000.0))
        self.assertIsNone(cast(CardChart, charts["Mean temperature"]).usual)


if __name__ == "__main__":
    unittest.main()
