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
        document["dashboard"]["pinned"] = []
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
        """Find a card's menu by its widget key.

        Args:
            app: The running app.
            key: The menu's key, e.g. ``menu-Body and health-activity.steps``.

        Returns:
            The menu button.
        """
        menus = (cast(MenuButton, menu) for menu in app.get("menu_button"))
        return next(menu for menu in menus if menu.key == key)

    def test_pin_hide_and_show_again(self):
        """The card menu pins and hides; the Hidden list brings things back."""
        config = Path(os.environ[CONFIG_ENV])
        app = AppTest.from_file(str(APP), default_timeout=30).run()

        self.menu(app, "menu-Body and health-activity.steps").click(
            "Pin card to the top"
        ).run()
        self.assertIn("Pinned", [header.value for header in app.subheader])
        self.assertIn('pinned = ["activity.steps"]', config.read_text(encoding="utf-8"))
        self.menu(app, "menu-pinned-activity.steps").click("Unpin card").run()
        self.assertNotIn("Pinned", [header.value for header in app.subheader])

        self.menu(app, "menu-Body and health-activity.steps").click(
            "Hide all of Activity"
        ).run()
        self.assertNotIn("Steps", [metric.label for metric in app.metric])
        saved = config.read_text(encoding="utf-8")
        self.assertIn('hidden = ["activity"]', saved)
        self.assertIn("# cards or categories left out", saved)
        app.switch_page("app_pages/trends.py").run()
        self.assertNotIn("Activity", app.pills(key="trend_category").options)
        self.assertIn("Sleep", app.pills(key="trend_category").options)

        app.switch_page("app_pages/overview.py").run()
        app.button(key="unhide-activity").click().run()
        self.assertIn("Steps", [metric.label for metric in app.metric])
        self.assertIn("hidden = []", config.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
