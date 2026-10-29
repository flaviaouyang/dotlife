import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from dotlife.config import DataSource, all_categories, context_for
from dotlife.journal import Entry, read_journal
from dotlife.schema import Category, Context, Grain, Row, row_parser


@dataclass(frozen=True, slots=True)
class Dataset:
    """Everything in a data folder, parsed once, for the dashboard and other readers.

    Attributes:
        source: The folder and settings it was read from.
        categories: Switched-on categories that have data, in FORMAT.md order.
        rows: Parsed rows by category name; rows that don't parse are skipped
            (the validator reports them).
        contexts: Settings by category name.
        journal: Journal entries, oldest first; empty without a journal folder.
    """

    source: DataSource
    categories: tuple[Category, ...]
    rows: Mapping[str, list[Row]]
    contexts: Mapping[str, Context]
    journal: tuple[Entry, ...]

    @property
    def as_of(self) -> date | None:
        """The latest date anywhere in the data, or None for an empty folder."""
        days = [
            cast(date, row["date"]) for rows in self.rows.values() for row in rows
        ] + [entry.day for entry in self.journal]
        return max(days, default=None)


def read_rows(category: Category, path: Path) -> list[Row]:
    """Read a category's CSV file into parsed rows, skipping rows that don't parse.

    Args:
        category: The category.
        path: Its data file.

    Returns:
        The rows that parse, in file order.
    """
    parse = row_parser(category)
    rows = []
    with path.open(newline="", encoding="utf-8-sig") as file:
        for raw in csv.DictReader(file):
            try:
                rows.append(parse(raw))
            except ValueError:
                continue
    return rows


def load_dataset(source: DataSource) -> Dataset:
    """Load every switched-on category that has a data file.

    Args:
        source: The data folder and its settings, from ``find_data``.

    Returns:
        The dataset.

    Raises:
        ValueError: If config.toml describes a custom metric or time zone wrongly.
    """
    contexts = {
        category.name: context_for(category, source.config)
        for category in all_categories(source.config)
    }
    present = [
        category
        for category in all_categories(source.config)
        if contexts[category.name].enabled
        and (source.folder / category.file.rstrip("/")).exists()
    ]
    rows = {
        category.name: read_rows(category, source.folder / category.file)
        for category in present
        if category.grain is not Grain.ENTRY
    }
    journal_folder = next(
        (
            source.folder / category.file
            for category in present
            if category.grain is Grain.ENTRY
        ),
        None,
    )
    journal = () if journal_folder is None else read_journal(journal_folder)
    return Dataset(source, tuple(present), rows, contexts, journal)
