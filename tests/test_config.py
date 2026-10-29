import tempfile
import unittest
from pathlib import Path

from dotlife.categories import ACTIVITY, MOOD
from dotlife.config import context_for, load_config

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


if __name__ == "__main__":
    unittest.main()
