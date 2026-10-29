import unittest
from pathlib import Path

from dotlife.config import find_data
from dotlife.validate import Severity, validate_folder

ROOT = Path(__file__).resolve().parent.parent


class SampleTest(unittest.TestCase):
    """The committed sample data validates, with only its planted warnings."""

    def setUp(self):
        """Validate sample/ with its own config.toml."""
        source = find_data(ROOT / "config.toml", ROOT / "sample")
        self.report = validate_folder(source.folder, source.config)

    def test_no_errors_and_every_category_present(self):
        """Every category has data, including the custom metric, and none has errors."""
        self.assertEqual(self.report.error_count, 0)
        self.assertEqual(self.report.missing, [])
        self.assertIn("experiments", {file.category for file in self.report.files})

    def test_only_planted_warnings(self):
        """The warnings are the long chase, the stale VO2 max and the Swiss trip."""
        warnings = {
            (problem.column, problem.message.split(";")[0].split(" (")[0])
            for problem in self.report.all_problems
            if problem.severity is Severity.WARNING
        }
        self.assertEqual(
            warnings,
            {
                ("steps", "62,000 is outside the usual 0 to 60,000"),
                ("vo2max_ml_kg_min", "unchanged since 2026-05-03"),
                (None, "currency CHF is not the home currency GBP"),
            },
        )


class FindDataTest(unittest.TestCase):
    """A data folder's own config.toml wins over the repo's."""

    def test_sample_uses_its_own_config(self):
        """The sample is read in London time with pounds, whatever the repo says."""
        source = find_data(ROOT / "config.toml", ROOT / "sample")
        self.assertEqual(source.config["timezone"], "Europe/London")
        self.assertIs(source.is_sample, False)

    def test_missing_folder(self):
        """A folder that doesn't exist raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            find_data(ROOT / "config.toml", ROOT / "no-such-folder")


if __name__ == "__main__":
    unittest.main()
