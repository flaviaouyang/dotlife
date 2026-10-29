import tempfile
import unittest
from datetime import date
from pathlib import Path

from dotlife.journal import Entry, read_journal


class EntryTest(unittest.TestCase):
    """Tags are words starting with #; the plain text drops them."""

    def test_tags_and_plain_text(self):
        """Tags keep their first-use order; repeats and mid-word hashes are ignored."""
        entry = Entry(
            date(2026, 1, 5), "Climbed. #climbing Then C# practice. #bob #climbing"
        )
        self.assertEqual(entry.tags, ("#climbing", "#bob"))
        self.assertEqual(entry.plain_text, "Climbed. Then C# practice.")


class ReadJournalTest(unittest.TestCase):
    """Only files named by a real date are read, oldest first."""

    def test_reads_named_files_in_order(self):
        """Misnamed files are skipped; text is stripped of surrounding blank lines."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, text in (
                ("2026-01-07.md", "Second.\n"),
                ("2026-01-05.md", "\nFirst.\n\n"),
                ("notes.md", "Not an entry."),
            ):
                (root / name).write_text(text, encoding="utf-8")
            entries = read_journal(root)
        self.assertEqual(
            entries,
            (Entry(date(2026, 1, 5), "First."), Entry(date(2026, 1, 7), "Second.")),
        )


if __name__ == "__main__":
    unittest.main()
