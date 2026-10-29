import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import vl_convert

from dotlife.categories import ACTIVITY, BODY
from dotlife.config import Goal, find_data, goal_for, goal_problems
from dotlife.dashboard.cards import CardChart, ChartKind, Selection, build_overview
from dotlife.dashboard.charts import card_chart
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


class CycleAndBudgetTest(unittest.TestCase):
    """The cycle card describes the cycle; spending compares with budgets."""

    def test_cycle_and_budgets_for_august(self):
        """Day 10 of the cycle; August's budgets as written in the sample config."""
        dataset = load_dataset(find_data(ROOT / "config.toml", ROOT / "sample"))
        cards = {
            card.label: card
            for card in build_overview(
                dataset, Selection(Period.MONTH, date(2026, 8, 1), True)
            ).cards
        }
        cycle = cards["Menstrual cycle"]
        self.assertEqual((cycle.value, cycle.unit), ("Day 10", "of cycle"))
        self.assertIn("Last period 21 Aug to 25 Aug", cycle.note)
        self.assertIn("next expected around 18 Sep", cycle.note)
        self.assertIn("books £43.91 of £40.00 (over)", cards["Spending"].note)
        self.assertIn("coffee £26.94 of £60.00", cards["Spending"].note)


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
        self.assertEqual(kinds["Spending"], ChartKind.BUDGET)
        self.assertEqual(kinds["Menstrual cycle"], ChartKind.CYCLE)
        self.assertIsNone(kinds["VO2 max"])
        steps = cast(CardChart, charts["Steps"])
        self.assertIsNotNone(steps.usual)
        self.assertEqual(steps.goals[-1], (date(2026, 8, 24), 10000.0))
        self.assertIsNone(cast(CardChart, charts["Mean temperature"]).usual)


class CardChartRenderTest(unittest.TestCase):
    """Every card chart draws, in both views; a valid spec alone isn't enough."""

    def test_all_charts_render(self):
        """Each chart renders to SVG with Vega, as a browser would draw it."""
        dataset = load_dataset(find_data(ROOT / "config.toml", ROOT / "sample"))
        for selection in (
            Selection(Period.WEEK, date(2026, 8, 24), True),
            Selection(Period.MONTH, date(2026, 7, 1), True),
        ):
            days = (selection.end - selection.start).days
            for card in build_overview(dataset, selection).cards:
                if card.chart is None:
                    continue
                with self.subTest(period=selection.period, card=card.label):
                    spec = card_chart(card.chart, card.color, selection.start, days)
                    svg = vl_convert.vegalite_to_svg(spec.to_dict())
                    self.assertIn("<svg", svg)


if __name__ == "__main__":
    unittest.main()


class InferredNoteTest(unittest.TestCase):
    """Cards say when values were inferred rather than recorded."""

    def test_mood_inferred_on_some_days(self):
        """Inferred days are counted against days with a value; the input named."""
        dataset = load_dataset(find_data(ROOT / "config.toml", ROOT / "sample"))
        inferred_days = {date(2026, 8, day) for day in (24, 25, 26)}
        mood = [
            row | {"source": "inferred-reflections"}
            if row["date"] in inferred_days
            else row
            for row in dataset.rows["mood"]
        ]
        dataset = replace(dataset, rows={**dataset.rows, "mood": mood})
        selection = Selection(Period.WEEK, date(2026, 8, 24), False)
        notes = {
            card.label: card.note for card in build_overview(dataset, selection).cards
        }
        week = {
            day
            for row in mood
            if date(2026, 8, 24)
            <= (day := cast(date, row["date"]))
            <= date(2026, 8, 30)
            and row.get("mood") is not None
        }
        expected = f"{len(week & inferred_days)} of {len(week)} days inferred"
        self.assertIn(f"{expected} from reflections", notes["Mood"])
        self.assertNotIn("inferred", notes["Steps"])
