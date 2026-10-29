import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from dotlife.categories import ACTIVITY, FITNESS_MARKERS, MOOD
from dotlife.config import context_for, load_config, plausible_range, related_metrics
from dotlife.schema import Context

ROOT = Path(__file__).resolve().parent.parent


class ConfigTest(unittest.TestCase):
    """config.toml loads, and each category sees its own section."""

    def test_repo_config_covers_every_option_the_rules_read(self):
        """The shipped config.toml has the watch-off thresholds activity needs."""
        context = context_for(ACTIVITY, load_config(ROOT / "config.toml"))
        self.assertIn("watch_off_steps", context.options)
        self.assertIn("watch_off_sedentary_min", context.options)

    def test_missing_section_is_empty(self):
        """A category without a config section gets empty options and is enabled."""
        context = context_for(MOOD, {"timezone": "UTC"})
        self.assertEqual(dict(context.options), {})
        self.assertIs(context.enabled, True)

    def test_timezone_errors(self):
        """A missing or unknown time zone raises a message that names the fix."""
        for config in ({}, {"timezone": "Mars/Olympus"}):
            with (
                self.subTest(config=config),
                self.assertRaisesRegex(ValueError, "config.toml: .*time"),
            ):
                context_for(MOOD, config)

    def test_load_config(self):
        """A TOML file loads into a dict."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.toml"
            path.write_text('timezone = "UTC"\n', encoding="utf-8")
            self.assertEqual(load_config(path), {"timezone": "UTC"})


class OverrideTest(unittest.TestCase):
    """Plausible bounds and related metrics default to the spec; config overrides."""

    steps = ACTIVITY.metrics[0]
    vo2max = FITNESS_MARKERS.metrics[0]

    def context(self, options: dict) -> Context:
        """Build a context with the given options.

        Args:
            options: The category's config section.

        Returns:
            The context.
        """
        return Context(ZoneInfo("UTC"), options)

    def test_plausible_default_and_override(self):
        """Without an override the spec's bounds apply; with one, config wins."""
        self.assertEqual(plausible_range(self.steps, self.context({})), (0, 60_000))
        override = self.context({"plausible": {"steps": [0, 150_000]}})
        self.assertEqual(plausible_range(self.steps, override), (0.0, 150_000.0))

    def test_bad_plausible_override(self):
        """Overrides that aren't two ordered numbers raise a message naming the key."""
        for bad in ([5], [10, 1], "high", [0, "x"]):
            with (
                self.subTest(bad=bad),
                self.assertRaisesRegex(ValueError, "plausible.steps"),
            ):
                plausible_range(self.steps, self.context({"plausible": {"steps": bad}}))

    def test_related_default_and_override(self):
        """An empty override list turns the stuck flag off."""
        self.assertEqual(
            related_metrics(self.vo2max, self.context({})),
            ("heart.resting_hr_bpm", "activity.active_min"),
        )
        off = self.context({"related": {"vo2max_ml_kg_min": []}})
        self.assertEqual(related_metrics(self.vo2max, off), ())


if __name__ == "__main__":
    unittest.main()
