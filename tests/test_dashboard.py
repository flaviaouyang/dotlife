import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from dotlife.config import CONFIG_ENV, DATA_ENV
from dotlife.periods import Period

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "dotlife" / "dashboard" / "app.py"
PAGES = (
    "app_pages/overview.py",
    "app_pages/trends.py",
    "app_pages/reflections.py",
    "app_pages/health.py",
)


class DashboardSmokeTest(unittest.TestCase):
    """Every page renders with the sample data, without exceptions."""

    def setUp(self):
        """Point the dashboard at the repo's config, which falls back to the sample."""
        self.saved = {name: os.environ.get(name) for name in (CONFIG_ENV, DATA_ENV)}
        os.environ[CONFIG_ENV] = str(ROOT / "config.toml")
        os.environ.pop(DATA_ENV, None)

    def tearDown(self):
        """Restore the environment."""
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_every_page_renders(self):
        """Each page runs to the end and shows the sample-data notice."""
        for page in PAGES:
            with self.subTest(page=page):
                app = AppTest.from_file(str(APP), default_timeout=30).run()
                app.switch_page(page).run()
                self.assertEqual(list(app.exception), [])
                self.assertIn("Sample data", [info.proto.title for info in app.info])

    def test_overview_cards_and_period_switch(self):
        """The Overview shows cards; switching to months keeps the same date range."""
        app = AppTest.from_file(str(APP), default_timeout=30).run()
        self.assertEqual(app.title[0].value, "Week of 24 August 2026")
        self.assertEqual(app.metric[0].label, "Steps")
        self.assertEqual(app.metric[0].value, "9,661")
        app.toggle(key="show_sensitive").set_value(True).run()
        self.assertIn("Spending", [metric.label for metric in app.metric])
        app.segmented_control(key="period").set_value(Period.MONTH).run()
        self.assertEqual(app.title[0].value, "August 2026")
        self.assertEqual(app.session_state["start"], date(2026, 8, 1))
        self.assertGreater(len(app.metric), 20)

    def test_only_activity_and_sleep(self):
        """A folder with just two files still gives a working dashboard."""
        with tempfile.TemporaryDirectory() as folder:
            for name in ("activity.csv", "sleep.csv", "config.toml"):
                shutil.copy(ROOT / "sample" / name, folder)
            os.environ[DATA_ENV] = folder
            for page in PAGES:
                with self.subTest(page=page):
                    app = AppTest.from_file(str(APP), default_timeout=30).run()
                    app.toggle(key="show_sensitive").set_value(True).run()
                    app.switch_page(page).run()
                    self.assertEqual(list(app.exception), [])
            app = AppTest.from_file(str(APP), default_timeout=30).run()
            labels = [metric.label for metric in app.metric]
            self.assertEqual(labels, ["Steps", "Active time", "Time asleep", "Bedtime"])


if __name__ == "__main__":
    unittest.main()
