import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import cast

import tomlkit
from streamlit.testing.v1 import AppTest
from streamlit.testing.v1.element_tree import MenuButton

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
        """Use a copy of the repo's config without pins, next to the sample.

        The copy keeps the tests independent of whatever the developer has pinned.
        """
        self.saved = {name: os.environ.get(name) for name in (CONFIG_ENV, DATA_ENV)}
        self.temp = tempfile.TemporaryDirectory()
        config = Path(self.temp.name) / "config.toml"
        document = tomlkit.parse((ROOT / "config.toml").read_text(encoding="utf-8"))
        for name in ("cards", "categories"):
            document["dashboard"][f"pinned_{name}"] = []
            document["dashboard"][f"hidden_{name}"] = []
        config.write_text(tomlkit.dumps(document), encoding="utf-8")
        shutil.copytree(ROOT / "sample", Path(self.temp.name) / "sample")
        os.environ[CONFIG_ENV] = str(config)
        os.environ.pop(DATA_ENV, None)

    def tearDown(self):
        """Restore the environment and remove the copy."""
        self.temp.cleanup()
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

    def menu(self, app: AppTest, key: str) -> MenuButton:
        """Find a menu by its widget key.

        Args:
            app: The running app.
            key: The menu's key, e.g. ``menu-Body and health-activity.steps``.

        Returns:
            The menu button.
        """
        menus = (cast(MenuButton, menu) for menu in app.get("menu_button"))
        return next(menu for menu in menus if menu.key == key)

    def test_pin_hide_and_show_card(self):
        """The card menu pins and hides one card; the Hidden list brings it back."""
        config = Path(os.environ[CONFIG_ENV])
        app = AppTest.from_file(str(APP), default_timeout=30).run()

        self.menu(app, "menu-Body and health-activity.steps").click(
            "Pin card to the top"
        ).run()
        self.assertIn("Pinned", [header.value for header in app.subheader])
        saved = config.read_text(encoding="utf-8")
        self.assertIn('pinned_cards = ["activity.steps"]', saved)
        self.menu(app, "menu-pinned-activity.steps").click("Unpin card").run()
        self.assertNotIn("Pinned", [header.value for header in app.subheader])

        self.menu(app, "menu-Body and health-activity.steps").click("Hide card").run()
        labels = [metric.label for metric in app.metric]
        self.assertNotIn("Steps", labels)
        self.assertIn("Active time", labels)
        saved = config.read_text(encoding="utf-8")
        self.assertIn('hidden_cards = ["activity.steps"]', saved)
        self.assertIn("# Overview cards left out", saved)
        app.switch_page("app_pages/trends.py").run()
        self.assertIn("Activity", app.pills(key="trend_category").options)

        app.switch_page("app_pages/overview.py").run()
        app.button(key="unhide-hidden_cards-activity.steps").click().run()
        self.assertIn("Steps", [metric.label for metric in app.metric])
        self.assertIn("hidden_cards = []", config.read_text(encoding="utf-8"))

    def test_pin_hide_and_show_category(self):
        """Trends pins and hides whole categories, apart from the Overview."""
        config = Path(os.environ[CONFIG_ENV])
        app = AppTest.from_file(str(APP), default_timeout=30).run()
        app.switch_page("app_pages/trends.py").run()

        self.menu(app, "category-menu-sleep").click("Hide Sleep").run()
        self.assertNotIn("Sleep", app.pills(key="trend_category").options)
        self.assertIn('hidden_categories = ["sleep"]', config.read_text("utf-8"))

        options = app.pills(key="trend_category").options
        self.assertNotEqual(options[0], "Mood")
        app.pills(key="trend_category").set_value("mood").run()
        self.menu(app, "category-menu-mood").click("Pin Mood to the front").run()
        self.assertEqual(app.pills(key="trend_category").options[0], "Mood")

        app.switch_page("app_pages/overview.py").run()
        self.assertIn("Time asleep", [metric.label for metric in app.metric])
        app.switch_page("app_pages/trends.py").run()
        app.button(key="unhide-hidden_categories-sleep").click().run()
        self.assertIn("Sleep", app.pills(key="trend_category").options)


if __name__ == "__main__":
    unittest.main()
