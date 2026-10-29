import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

FILE_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})\.md")
TAG = re.compile(r"(?<!\S)#[\w-]+")
SPACES = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Entry:
    """One day's journal entry.

    Attributes:
        day: The local date the entry is filed under.
        text: The entry as written, tags included.
    """

    day: date
    text: str

    @property
    def tags(self) -> tuple[str, ...]:
        """The entry's ``#tags``, in order of first use, without repeats."""
        return tuple(dict.fromkeys(TAG.findall(self.text)))

    @property
    def plain_text(self) -> str:
        """The entry with its tags removed and its whitespace tidied."""
        return SPACES.sub(" ", TAG.sub("", self.text)).strip()


def journal_date(name: str) -> date | None:
    """Return the date a journal file is named after.

    Args:
        name: A file name, e.g. ``2026-03-08.md``.

    Returns:
        The date, or None when the name isn't a real ``YYYY-MM-DD.md`` date.

    Example:
        >>> journal_date("2026-03-08.md")
        datetime.date(2026, 3, 8)
        >>> journal_date("2026-02-30.md") is None
        True
    """
    match = FILE_NAME.fullmatch(name)
    if match is None:
        return None
    try:
        return date.fromisoformat(match[1])
    except ValueError:
        return None


def read_journal(folder: Path) -> tuple[Entry, ...]:
    """Read every correctly named entry in a journal folder.

    Files that aren't named ``YYYY-MM-DD.md`` are skipped; the validator reports
    them.

    Args:
        folder: The journal folder.

    Returns:
        Entries, oldest first.
    """
    entries = []
    for path in sorted(folder.iterdir()):
        day = journal_date(path.name)
        if day is None:
            continue
        with path.open(encoding="utf-8") as file:
            entries.append(Entry(day, file.read().strip()))
    return tuple(entries)
