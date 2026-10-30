import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from dotlife.cli import main
from dotlife.fresh import LOG_FILE, fresh_steps

WRITE_MOOD = """\
import os
from pathlib import Path

data = Path(os.environ["DOTLIFE_DATA"])
(data / "mood.csv").write_text("date,source,mood\\n2026-01-05,app,4\\n")
print("wrote mood.csv")
"""
STAGE_MOOD = """\
from datetime import date

from dotlife.staging import from_env

staging = from_env()
staging.write("{source}", "mood", [{{"date": date(2026, 1, {day}), "mood": {mood}}}])
"""
FAIL = 'import sys\nprint("token expired")\nsys.exit(3)\n'
WRITE_BAD_MOOD = """\
import os
from pathlib import Path

data = Path(os.environ["DOTLIFE_DATA"])
(data / "mood.csv").write_text("date,source,mood\\n2026-01-05,app,9\\n")
"""


class FreshStepsTest(unittest.TestCase):
    """Steps are read from config.toml and checked."""

    def test_script_and_command(self):
        """A script runs with dotlife's Python; a command runs as written."""
        steps = fresh_steps(
            {
                "fresh": {
                    "steps": [
                        {"name": "oura", "script": "scripts/oura.py"},
                        {"name": "calendar", "command": ["swift", "cal.swift"]},
                        {"name": "mood", "agent": "prompts/mood.md"},
                    ]
                }
            }
        )
        self.assertEqual([step.name for step in steps], ["oura", "calendar", "mood"])
        self.assertEqual(steps[0].argv[1:], ("scripts/oura.py",))
        self.assertEqual(steps[1].argv, ("swift", "cal.swift"))
        self.assertEqual((steps[2].needs_agent, steps[2].argv), (True, ()))

    def test_malformed_steps(self):
        """Missing names, both or neither runner, and repeats are errors."""
        cases = {
            "needs a name": [{"script": "a.py"}],
            "exactly one of": [{"name": "a"}],
            "exactly one of script": [
                {"name": "a", "script": "a.py", "command": ["a"]}
            ],
            "agent must be a path": [{"name": "a", "agent": True}],
            "must be a list": [{"name": "a", "command": "swift a"}],
            "must be unique: a": [
                {"name": "a", "script": "a.py"},
                {"name": "a", "script": "b.py"},
            ],
        }
        for message, steps in cases.items():
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                fresh_steps({"fresh": {"steps": steps}})


class FreshRunTest(unittest.TestCase):
    """``dotlife fresh`` runs every step, then validates, and keeps a log."""

    def setUp(self):
        """Create a repo folder with an empty scripts folder."""
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()

    def tearDown(self):
        """Delete the repo folder."""
        self.temp.cleanup()

    def run_fresh(self, scripts: dict[str, str], *args: str) -> tuple[int, str]:
        """Write scripts and a config listing them in order, then run fresh.

        Args:
            scripts: Script source by step name.
            *args: Extra arguments.

        Returns:
            The exit code and what was printed.
        """
        tables = []
        for name, source in scripts.items():
            (self.root / "scripts" / f"{name}.py").write_text(source, encoding="utf-8")
            tables.append(
                f'[[fresh.steps]]\nname = "{name}"\nscript = "scripts/{name}.py"\n'
            )
        config = self.root / "config.toml"
        config.write_text(
            'format_version = 1\ntimezone = "UTC"\n\n' + "\n".join(tables),
            encoding="utf-8",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = main(["fresh", "--config", str(config), *args])
        return code, output.getvalue()

    def test_steps_write_data_then_validate(self):
        """Scripts write into data/, which is created; the run ends validated."""
        code, output = self.run_fresh({"mood": WRITE_MOOD})
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "data" / "mood.csv").is_file())
        self.assertIn("  wrote mood.csv", output)
        self.assertIn("1 of 1 steps finished. Validation: 0 errors.", output)
        log = (self.root / LOG_FILE).read_text(encoding="utf-8")
        self.assertIn("wrote mood.csv", log)

    def test_staged_rows_are_merged_by_rank(self):
        """Scripts stage rows per source; the run merges them into data/."""
        scripts = {
            "notes": STAGE_MOOD.format(source="notes", day=5, mood=4),
            "inferred": STAGE_MOOD.format(source="inferred-reflections", day=6, mood=2),
        }
        for name, source in scripts.items():
            (self.root / "scripts" / f"{name}.py").write_text(source, encoding="utf-8")
        config = self.root / "config.toml"
        config.write_text(
            'format_version = 1\ntimezone = "UTC"\ntrack = ["mood"]\n\n'
            '[sources]\nmood = ["notes", "inferred-reflections"]\n\n'
            + "\n".join(
                f'[[fresh.steps]]\nname = "{name}"\nscript = "scripts/{name}.py"\n'
                for name in scripts
            ),
            encoding="utf-8",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = main(["fresh", "--config", str(config)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertIn(
            "mood.csv: 2 rows from notes, inferred-reflections", output.getvalue()
        )
        self.assertEqual(
            (self.root / "data" / "mood.csv").read_text(encoding="utf-8"),
            "date,source,mood\n2026-01-05,notes,4\n2026-01-06,inferred-reflections,2\n",
        )

    def test_a_failed_step_does_not_stop_the_others(self):
        """Every step runs; the failure is named and the exit code is 1."""
        code, output = self.run_fresh({"oura": FAIL, "mood": WRITE_MOOD})
        self.assertEqual(code, 1)
        self.assertIn("token expired", output)
        self.assertIn("failed (exit code 3)", output)
        self.assertIn("1 of 2 steps finished; 1 failed: oura.", output)
        self.assertTrue((self.root / "data" / "mood.csv").is_file())

    def test_agent_steps_are_listed_not_run(self):
        """A step for the agent is named in the summary and isn't a failure."""
        config = self.root / "config.toml"
        config.write_text(
            'format_version = 1\ntimezone = "UTC"\n\n[[fresh.steps]]\n'
            'name = "mood"\nagent = "prompts/mood.md"\n',
            encoding="utf-8",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["fresh", "--config", str(config)])
        self.assertEqual(code, 0)
        self.assertIn("following prompts/mood.md", output.getvalue())
        self.assertIn(
            "0 of 0 steps finished; 1 for your agent's fetch skill: mood.",
            output.getvalue(),
        )

    def test_invalid_data_fails_the_run(self):
        """A step that finishes but writes bad values still fails the run."""
        code, output = self.run_fresh({"mood": WRITE_BAD_MOOD})
        self.assertEqual(code, 1)
        self.assertIn("Validation: 1 error.", output)

    def test_only_and_missing_steps(self):
        """--only runs one step; an unknown name or no steps is a usage error."""
        code, output = self.run_fresh(
            {"oura": FAIL, "mood": WRITE_MOOD}, "--only", "mood"
        )
        self.assertEqual(code, 0)
        self.assertNotIn("token expired", output)
        code, output = self.run_fresh({"mood": WRITE_MOOD}, "--only", "oura")
        self.assertEqual((code, "no step named 'oura'" in output), (2, True))
        code, output = self.run_fresh({})
        self.assertEqual((code, "no [[fresh.steps]]" in output), (2, True))

    def test_hand_entries_alone_are_merged(self):
        """With no steps, rows staged by hand are still merged and validated."""
        manual = self.root / "data" / "sources" / "manual"
        manual.mkdir(parents=True)
        (manual / "mood.csv").write_text("date,source,mood\n2026-01-05,manual,4\n")
        config = self.root / "config.toml"
        config.write_text(
            'format_version = 1\ntimezone = "UTC"\ntrack = ["mood"]\n\n'
            '[sources]\nmood = ["manual"]\n',
            encoding="utf-8",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["fresh", "--config", str(config)])
        self.assertEqual(code, 0, output.getvalue())
        self.assertIn("mood.csv: 1 row from manual", output.getvalue())
