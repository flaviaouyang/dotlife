import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from dotlife.reflections import parse_reflections, read_reflections

JRNL_FORMAT = "%Y-%m-%d %I:%M:%S %p"


class ParseTest(unittest.TestCase):
    """Entries split the jrnl way: a timestamp line starts each one."""

    def test_several_a_day_with_body_lines_and_stars(self):
        """Lines after a header belong to it, blank ones included, until the next."""
        text = (
            "[2026-08-24 08:12] Coffee first. #work\n"
            "[2026-08-24 22:40] Long day.\n"
            "\n"
            "Bed soon. @bob *\n"
        )
        parsed = parse_reflections(text, "%Y-%m-%d %H:%M", "#@")
        self.assertEqual(
            [(r.time, r.text, r.starred, r.tags, r.line) for r in parsed.reflections],
            [
                (
                    datetime(2026, 8, 24, 8, 12),
                    "Coffee first. #work",
                    False,
                    ("#work",),
                    1,
                ),
                (
                    datetime(2026, 8, 24, 22, 40),
                    "Long day.\n\nBed soon. @bob",
                    True,
                    ("@bob",),
                    2,
                ),
            ],
        )

    def test_jrnl_time_format(self):
        """A jrnl file reads directly once its time format is set."""
        parsed = parse_reflections(
            "[2026-03-08 09:05:00 PM] Late walk.\n", JRNL_FORMAT, "#@"
        )
        self.assertEqual(parsed.reflections[0].time, datetime(2026, 3, 8, 21, 5))

    def test_stray_lines_and_unparsable_brackets(self):
        """Text before the first entry is stray; a bracket that isn't a time is text."""
        text = (
            "notes to self\n\n"
            "[2026-01-05 10:00] Meeting. [link] here\n"
            "[not a time] still it\n"
        )
        parsed = parse_reflections(text, "%Y-%m-%d %H:%M", "#")
        self.assertEqual(parsed.stray_lines, (1,))
        self.assertEqual(
            parsed.reflections[0].text, "Meeting. [link] here\n[not a time] still it"
        )


class ReadTest(unittest.TestCase):
    """Yearly files are read together, oldest first; other files are skipped."""

    def test_reads_years_in_order(self):
        """Two years and a stray file give the entries in time order."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "2026.txt").write_text(
                "[2026-01-02 09:00] New year.\n", encoding="utf-8"
            )
            (root / "2025.txt").write_text(
                "[2025-12-31 23:00] Old year.\n", encoding="utf-8"
            )
            (root / "notes.md").write_text("ignored", encoding="utf-8")
            texts = [r.text for r in read_reflections(root, {})]
        self.assertEqual(texts, ["Old year.", "New year."])


if __name__ == "__main__":
    unittest.main()
