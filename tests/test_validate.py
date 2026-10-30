import contextlib
import csv
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from dotlife.cli import main
from dotlife.validate import Report, Severity, validate_folder

CONFIG = {
    "format_version": 1,
    "timezone": "America/New_York",
    "activity": {"watch_off_steps": 1000, "watch_off_sedentary_min": 480},
}


def write_csv(folder: Path, name: str, rows: list[list[str]]) -> None:
    """Write a CSV file.

    Args:
        folder: Where to write it.
        name: File name.
        rows: The header row, then data rows.
    """
    with (folder / name).open("w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerows(rows)


class ValidatorTestCase(unittest.TestCase):
    """Runs each test in a fresh, empty data folder."""

    def setUp(self):
        """Create the data folder."""
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)

    def tearDown(self):
        """Delete the data folder."""
        self.temp.cleanup()

    def validate(self, config: dict | None = None) -> Report:
        """Validate the data folder.

        Args:
            config: config.toml contents; the default config when None.

        Returns:
            The report.
        """
        return validate_folder(self.data, CONFIG if config is None else config)

    def messages(self, report: Report, severity: Severity) -> list[str]:
        """List the messages of one severity, with their columns.

        Args:
            report: The report.
            severity: Which problems to list.

        Returns:
            ``column: message`` strings, or just messages for problems without one.
        """
        return [
            f"{problem.column}: {problem.message}"
            if problem.column
            else problem.message
            for problem in report.all_problems
            if problem.severity is severity
        ]


class CsvValidationTest(ValidatorTestCase):
    """Problems in CSV files are found and placed."""

    def test_clean_file(self):
        """A valid file has no problems and reports its span."""
        write_csv(
            self.data,
            "mood.csv",
            [
                ["date", "source", "mood"],
                ["2026-01-05", "app", "4"],
                ["2026-01-06", "app", ""],
            ],
        )
        report = self.validate()
        self.assertEqual(report.all_problems, [])
        (mood,) = report.files
        self.assertEqual(
            (mood.rows, mood.first_date, mood.last_date),
            (2, date(2026, 1, 5), date(2026, 1, 6)),
        )

    def test_header_problems(self):
        """A missing required column is an error; an unknown one is a warning."""
        write_csv(
            self.data,
            "mood.csv",
            [["date", "mood", "colour"], ["2026-01-05", "4", "blue"]],
        )
        report = self.validate()
        self.assertEqual(
            self.messages(report, Severity.ERROR),
            ["source: required column is missing"],
        )
        self.assertEqual(
            self.messages(report, Severity.WARNING),
            ["colour: unknown column; it is ignored"],
        )

    def test_values(self):
        """Unparsable and impossible values are errors; unlikely ones are warnings."""
        write_csv(
            self.data,
            "activity.csv",
            [
                ["date", "source", "steps", "active_min"],
                ["2026-01-05", "watch", "lots", ""],
                ["2026-01-06", "watch", "-5", "2000"],
                ["2026-01-07", "watch", "70000", ""],
            ],
        )
        report = self.validate()
        errors = self.messages(report, Severity.ERROR)
        self.assertEqual(len(errors), 3)
        self.assertIn("steps: -5 is below the minimum 0", errors)
        self.assertIn("active_min: 2000 is above the maximum 1440", errors)
        self.assertEqual(len(self.messages(report, Severity.WARNING)), 1)
        lines = [problem.line for problem in report.all_problems]
        self.assertEqual(lines, [2, 3, 3, 4])

    def test_plausible_override(self):
        """Widening a plausible bound in config silences the warning."""
        write_csv(
            self.data,
            "activity.csv",
            [["date", "source", "steps"], ["2026-01-05", "watch", "70000"]],
        )
        config = CONFIG | {
            "activity": CONFIG["activity"] | {"plausible": {"steps": [0, 150_000]}}
        }
        self.assertEqual(self.validate(config).all_problems, [])

    def test_duplicates(self):
        """A repeated key is an error pointing at the first line."""
        write_csv(
            self.data,
            "mood.csv",
            [
                ["date", "source", "mood"],
                ["2026-01-05", "app", "4"],
                ["2026-01-05", "manual", "3"],
            ],
        )
        (problem,) = self.validate().all_problems
        self.assertEqual(
            (problem.line, problem.message),
            (3, "duplicate of line 2 (date must be unique)"),
        )

    def test_dates_after_today(self):
        """Rows dated in the future are a warning naming the last one."""
        write_csv(
            self.data,
            "mood.csv",
            [
                ["date", "source", "mood"],
                ["2026-01-05", "app", "4"],
                ["2999-01-01", "app", "3"],
                ["2999-01-02", "app", "3"],
            ],
        )
        self.assertEqual(
            self.messages(self.validate(), Severity.WARNING),
            [
                "2 days after today, up to 2999-01-02; check the source's clock "
                "and how its dates are worked out"
            ],
        )

    def test_inferred_source_names_its_input(self):
        """A bare inferred source is an error; inferred-<input> is fine."""
        write_csv(
            self.data,
            "mood.csv",
            [
                ["date", "source", "mood"],
                ["2026-01-05", "inferred", "4"],
                ["2026-01-06", "inferred-reflections", "3"],
            ],
        )
        self.assertEqual(
            self.messages(self.validate(), Severity.ERROR),
            ["source 'inferred' must name its input, e.g. inferred-reflections"],
        )

    def test_time_in_a_day(self):
        """Hours across categories can't add up to more than a day."""
        write_csv(
            self.data,
            "time.csv",
            [
                ["date", "category", "source", "hours"],
                ["2026-01-05", "work", "calendar", "16"],
                ["2026-01-05", "family", "calendar", "9.5"],
                ["2026-01-06", "work", "calendar", "8"],
            ],
        )
        self.assertEqual(
            self.messages(self.validate(), Severity.ERROR),
            ["hours: 2026-01-05 adds up to 25.5 across rows, more than 24 in a day"],
        )

    def test_category_checks(self):
        """Plug-in checks run: a night filed under its bedtime date is an error."""
        write_csv(
            self.data,
            "sleep.csv",
            [
                ["date", "start", "end", "source", "asleep_min"],
                [
                    "2026-03-07",
                    "2026-03-07T23:30-05:00",
                    "2026-03-08T07:30-04:00",
                    "watch",
                    "420",
                ],
            ],
        )
        (error,) = self.messages(self.validate(), Severity.ERROR)
        self.assertIn("wake date 2026-03-08", error)

    def test_gaps_and_skipped_days(self):
        """Missing days are gaps; watch-off days are counted, not dropped."""
        write_csv(
            self.data,
            "activity.csv",
            [
                ["date", "source", "steps", "sedentary_min"],
                ["2026-01-01", "watch", "8000", "600"],
                ["2026-01-02", "watch", "200", "100"],
                ["2026-01-05", "watch", "9000", "500"],
            ],
        )
        (activity,) = self.validate().files
        self.assertEqual(activity.gaps, [(date(2026, 1, 3), date(2026, 1, 4))])
        self.assertEqual(activity.days_skipped, 1)

    def test_stale_value(self):
        """A value unchanged for longer than stale_after_days is a warning."""
        write_csv(
            self.data,
            "fitness_markers.csv",
            [
                ["date", "source", "vo2max_ml_kg_min"],
                ["2026-01-01", "watch", "38"],
                ["2026-02-01", "watch", "38"],
            ],
        )
        write_csv(
            self.data,
            "mood.csv",
            [["date", "source", "mood"], ["2026-05-01", "app", "3"]],
        )
        config = CONFIG | {
            "fitness_markers": {"stale_after_days": {"vo2max_ml_kg_min": 90}}
        }
        (warning,) = self.messages(self.validate(config), Severity.WARNING)
        self.assertIn("unchanged since 2026-01-01 (120 days)", warning)

    def test_currency_warning(self):
        """A transaction in another currency than home_currency is a warning."""
        write_csv(
            self.data,
            "finances.csv",
            [
                ["date", "category", "currency", "source", "amount"],
                ["2026-01-05", "travel", "USD", "bank", "-40"],
            ],
        )
        config = CONFIG | {"finances": {"home_currency": "EUR"}}
        (warning,) = self.messages(self.validate(config), Severity.WARNING)
        self.assertIn("USD is not the home currency EUR", warning)


class FolderValidationTest(ValidatorTestCase):
    """Folder-level behaviour: switched-off, missing, reflections, custom metrics."""

    def test_missing_and_disabled(self):
        """Disabled categories aren't read even when their file has errors."""
        write_csv(self.data, "mood.csv", [["broken"]])
        report = self.validate(CONFIG | {"mood": {"enabled": False}})
        self.assertIn("mood", report.disabled)
        self.assertIn("activity", report.missing)
        self.assertEqual(report.error_count, 0)

    def test_reflections(self):
        """Entries are counted; misfiled entries and stray text are flagged."""
        folder = self.data / "reflections"
        folder.mkdir()
        (folder / "2026.txt").write_text(
            "loose note\n"
            "[2026-01-05 08:00] Morning. #outside\n"
            "[2025-12-31 23:00] Wrong year.\n",
            encoding="utf-8",
        )
        (folder / "notes.md").write_text("ignored", encoding="utf-8")
        report = self.validate()
        (reflections,) = report.files
        self.assertEqual(reflections.rows, 2)
        self.assertEqual(len(self.messages(report, Severity.WARNING)), 2)
        (error,) = self.messages(report, Severity.ERROR)
        self.assertIn("belongs in 2025.txt", error)

    def test_reflection_after_now(self):
        """An entry timed in the future is a warning on its line."""
        folder = self.data / "reflections"
        folder.mkdir()
        (folder / "2999.txt").write_text(
            "[2999-01-05 08:00] From the future.\n", encoding="utf-8"
        )
        (warning,) = [
            problem
            for problem in self.validate().all_problems
            if problem.severity is Severity.WARNING
        ]
        self.assertEqual(warning.line, 1)
        self.assertIn(
            "1 entry timed after now, up to 2999-01-05 08:00", warning.message
        )

    def test_custom_metric(self):
        """A custom metric from config is validated like a built-in one."""
        write_csv(
            self.data,
            "guitar.csv",
            [["date", "source", "value"], ["2026-01-05", "manual", "2000"]],
        )
        config = CONFIG | {
            "custom": {
                "guitar": {
                    "label": "Guitar",
                    "unit": "min",
                    "summary": "sum",
                    "maximum": 1440,
                }
            }
        }
        self.assertEqual(
            self.messages(self.validate(config), Severity.ERROR),
            ["value: 2000 is above the maximum 1440"],
        )

    def test_config_errors(self):
        """Config mistakes are reported as errors, not raised."""
        cases = {
            "format_version": CONFIG | {"format_version": 2},
            "custom": CONFIG
            | {"custom": {"sleep": {"label": "x", "unit": "x", "summary": "sum"}}},
        }
        for case, config in cases.items():
            with self.subTest(case=case):
                self.assertEqual(self.validate(config).error_count, 1)


class CliTest(ValidatorTestCase):
    """The command's exit codes and output formats."""

    def run_cli(self, *args: str) -> tuple[int, str]:
        """Run ``dotlife validate`` on the data folder with a config written there.

        Args:
            *args: Extra arguments.

        Returns:
            The exit code and what was printed.
        """
        config = self.data / "config.toml"
        config.write_text('format_version = 1\ntimezone = "UTC"\n', encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["validate", str(self.data), "--config", str(config), *args])
        return code, output.getvalue()

    def test_exit_codes(self):
        """0 for a clean folder, 1 when there are errors."""
        write_csv(
            self.data,
            "mood.csv",
            [["date", "source", "mood"], ["2026-01-05", "app", "4"]],
        )
        code, output = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("0 errors, 0 warnings in 1 category.", output)
        write_csv(
            self.data,
            "mood.csv",
            [["date", "source", "mood"], ["2026-01-05", "app", "9"]],
        )
        self.assertEqual(self.run_cli()[0], 1)

    def test_json(self):
        """--json prints the report with counts, readable by other programs."""
        write_csv(
            self.data,
            "mood.csv",
            [["date", "source", "mood"], ["2026-01-05", "app", "4"]],
        )
        code, output = self.run_cli("--json")
        data = json.loads(output)
        self.assertEqual(
            (code, data["error_count"], data["as_of"]), (0, 0, "2026-01-05")
        )

    def test_missing_config(self):
        """An unreadable config exits with 2."""
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["validate", "--config", str(self.data / "nope.toml")])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
