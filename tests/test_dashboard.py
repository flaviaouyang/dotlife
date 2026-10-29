import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from dotlife.config import CONFIG_ENV, DATA_ENV

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "dotlife" / "dashboard" / "app.py"
PAGES = (
    "app_pages/overview.py",
    "app_pages/trends.py",
    "app_pages/journal.py",
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


if __name__ == "__main__":
    unittest.main()
