import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from dotlife.staging import Staging, merge

CONFIG: dict[str, Any] = {
    "format_version": 1,
    "timezone": "UTC",
    "track": ["mood", "sleep", "finances", "reflections", "activity"],
    "sources": {
        "mood": ["obsidian-daily-notes", "inferred-reflections"],
        "sleep": ["oura", "apple-health"],
        "finances": ["bank-a", "bank-b"],
        "reflections": ["jrnl", "obsidian-daily-notes"],
        "activity": ["apple-health"],
    },
}


class StagingTest(unittest.TestCase):
    """Scripts stage rows per source; make fresh merges them by rank."""

    def setUp(self):
        """Create an empty data folder."""
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name)
        self.staging = Staging(CONFIG, self.data)

    def tearDown(self):
        """Delete the data folder."""
        self.temp.cleanup()

    def text(self, *parts: str) -> str:
        """Read a file under the data folder.

        Args:
            *parts: Its path inside the data folder.

        Returns:
            Its contents.
        """
        return self.data.joinpath(*parts).read_text(encoding="utf-8")

    def test_write_is_sorted_and_repeatable(self):
        """Rows are sorted, formatted, and replaced rather than appended."""
        rows = [
            {"date": date(2026, 3, 3), "mood": 4.0},
            {"date": date(2026, 3, 2), "mood": 3, "energy": None},
        ]
        for _ in range(2):
            self.staging.write("obsidian-daily-notes", "mood", rows)
        self.assertEqual(
            self.text("sources", "obsidian-daily-notes", "mood.csv"),
            "date,source,mood,energy\n"
            "2026-03-02,obsidian-daily-notes,3,\n"
            "2026-03-03,obsidian-daily-notes,4,\n",
        )

    def test_window_keeps_older_rows(self):
        """A window replaces only its own dates."""
        days = [date(2026, 3, 1) + timedelta(days=offset) for offset in range(4)]
        self.staging.write(
            "apple-health", "activity", [{"date": d, "steps": 1} for d in days]
        )
        self.staging.write(
            "apple-health",
            "activity",
            [{"date": days[3], "steps": 2, "source": "apple-watch"}],
            window=(days[2], days[3]),
        )
        self.assertEqual(
            self.text("sources", "apple-health", "activity.csv").splitlines()[1:],
            [
                "2026-03-01,apple-health,1",
                "2026-03-02,apple-health,1",
                "2026-03-04,apple-watch,2",
            ],
        )

    def test_write_rejects_mistakes(self):
        """Unknown columns, missing dates and naive timestamps are errors."""
        with self.assertRaisesRegex(ValueError, "no column happiness"):
            self.staging.write(
                "x", "mood", [{"date": date(2026, 3, 2), "happiness": 1}]
            )
        with self.assertRaisesRegex(ValueError, "needs a date"):
            self.staging.write("x", "mood", [{"mood": 1}])
        with self.assertRaisesRegex(ValueError, "needs a time zone"):
            self.staging.write(
                "x",
                "sleep",
                [{"date": date(2026, 3, 2), "start": datetime(2026, 3, 1, 23)}],
            )

    def test_wants(self):
        """Only listed sources of switched-on categories are wanted."""
        self.assertTrue(self.staging.wants("apple-health", "sleep"))
        self.assertFalse(self.staging.wants("whoop", "sleep"))
        self.assertFalse(self.staging.wants("apple-health", "heart"))

    def test_merge_ranks_per_date(self):
        """The best source with a date wins all of that date's rows."""
        self.staging.write(
            "inferred-reflections",
            "mood",
            [{"date": date(2026, 3, d), "mood": 2} for d in (2, 3)],
        )
        self.staging.write(
            "obsidian-daily-notes", "mood", [{"date": date(2026, 3, 3), "mood": 5}]
        )
        night = {
            "date": date(2026, 3, 3),
            "start": datetime(2026, 3, 2, 23, tzinfo=UTC),
            "end": datetime(2026, 3, 3, 7, tzinfo=UTC),
        }
        self.staging.write(
            "apple-health",
            "sleep",
            [night, night | {"start": datetime(2026, 3, 3, 3, tzinfo=UTC)}],
        )
        self.staging.write("oura", "sleep", [night | {"asleep_min": 420}])
        self.staging.write("whoop", "sleep", [night])
        lines = merge(self.data, CONFIG)
        self.assertEqual(
            self.text("mood.csv").splitlines()[1:],
            ["2026-03-02,inferred-reflections,2", "2026-03-03,obsidian-daily-notes,5"],
        )
        self.assertEqual(len(self.text("sleep.csv").splitlines()), 2)
        self.assertIn("sleep.csv: 1 row from oura, apple-health", lines)
        self.assertIn(
            "sleep.csv: left out whoop, because [sources] doesn't list it", lines
        )

    def test_sessions_rank_by_overlapping_time(self):
        """A better source wins a shared session; one only a lower source has stays."""

        def session(day: int, start: int, hours: int, minutes: int) -> dict:
            begin = datetime(2026, 3, day, start, tzinfo=UTC)
            end = begin + timedelta(hours=hours)
            return {
                "date": end.date(),
                "start": begin,
                "end": end,
                "asleep_min": minutes,
            }

        self.staging.write("oura", "sleep", [session(2, 14, 1, 40)])
        self.staging.write(
            "apple-health",
            "sleep",
            [session(1, 23, 8, 397), session(2, 14, 1, 35), session(2, 23, 8, 410)],
        )
        merge(self.data, CONFIG)
        rows = self.text("sleep.csv").splitlines()[1:]
        self.assertEqual(
            [(row.split(",")[3], row.split(",")[4]) for row in rows],
            [("apple-health", "397"), ("oura", "40"), ("apple-health", "410")],
        )

    def test_merge_reports_values_left_out(self):
        """A lower source's value the winning row lacks is named, not lost quietly."""
        config = CONFIG | {
            "track": ["body"],
            "sources": {"body": ["apple-health", "manual"]},
        }
        staging = Staging(config, self.data)
        day = date(2026, 3, 2)
        staging.write("apple-health", "body", [{"date": day, "weight_kg": 71.2}])
        staging.write("manual", "body", [{"date": day, "waist_cm": 80}])
        lines = merge(self.data, config)
        self.assertIn(
            "body.csv: waist_cm from manual left out on 1 day, when a higher-ranked "
            "source had the day",
            lines,
        )

    def test_merge_keeps_every_transaction(self):
        """Rows that can repeat keep every source's rows."""
        for bank in ("bank-a", "bank-b"):
            self.staging.write(
                bank,
                "finances",
                [
                    {
                        "date": date(2026, 3, 2),
                        "account": bank,
                        "amount": -4.5,
                        "currency": "EUR",
                        "category": "coffee",
                    }
                ],
            )
        merge(self.data, CONFIG)
        self.assertEqual(len(self.text("finances.csv").splitlines()), 3)

    def test_merge_reflections_per_date(self):
        """Reflections come from the best source with entries that day."""
        for source, text in {
            "jrnl": "[2026-03-02 21:00] From jrnl.\nSecond line.\n",
            "obsidian-daily-notes": "[2026-03-02 08:00] Obsidian.\n\n"
            "[2026-03-03 08:00] Only here.\n",
        }.items():
            folder = self.staging.path(source, "reflections")
            folder.mkdir(parents=True)
            (folder / "2026.txt").write_text(text, encoding="utf-8")
        merge(self.data, CONFIG)
        self.assertEqual(
            self.text("reflections", "2026.txt"),
            "[2026-03-02 21:00] From jrnl.\nSecond line.\n\n"
            "[2026-03-03 08:00] Only here.\n",
        )

    def test_unstaged_and_switched_off_files_are_untouched(self):
        """A file nothing stages stays as written; an untracked category is skipped."""
        (self.data / "habits.csv").write_text("by hand\n", encoding="utf-8")
        self.staging.write(
            "apple-health", "heart", [{"date": date(2026, 3, 2), "hrv_ms": 50}]
        )
        lines = merge(self.data, CONFIG)
        self.assertEqual(self.text("habits.csv"), "by hand\n")
        self.assertFalse((self.data / "heart.csv").exists())
        self.assertEqual(
            lines, ["heart.csv: left out apple-health, because it is switched off"]
        )


if __name__ == "__main__":
    unittest.main()
