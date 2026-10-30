import csv
import io
import math
import os
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotlife.config import (
    CONFIG_ENV,
    DATA_ENV,
    all_categories,
    context_for,
    load_config,
)
from dotlife.reflections import header_time, settings
from dotlife.schema import Category, Grain
from dotlife.validate import plural

SOURCES_DIR = "sources"
Cell = str | float | int | date | datetime | None


def cell_text(value: Cell) -> str:
    """Write one value the way the format wants it.

    Args:
        value: A number, date, timestamp, text, or None for missing.

    Returns:
        The cell: empty for None, ISO 8601 for dates and timestamps, plain decimals
        for numbers.

    Raises:
        ValueError: For a timestamp without a time zone, or a number that isn't
            finite.

    Example:
        >>> [cell_text(v) for v in (None, 8421.0, 71.456789, date(2026, 3, 2))]
        ['', '8421', '71.456789', '2026-03-02']
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError(f"timestamp {value} needs a time zone")
        whole_minute = value.second == 0 and value.microsecond == 0
        return value.isoformat(timespec="minutes" if whole_minute else "seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    if not math.isfinite(value):
        raise ValueError(f"{value} is not a finite number")
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV file as text cells.

    Args:
        path: The file; it may not exist.

    Returns:
        Its header and rows; both empty for a missing file.
    """
    if not path.is_file():
        return [], []
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), list(reader)


def table_text(header: Sequence[str], rows: Iterable[Mapping[str, str]]) -> str:
    """Write rows as CSV text.

    Args:
        header: The columns, in order.
        rows: Cells by column; missing columns are written empty.

    Returns:
        The file's contents.
    """
    with io.StringIO() as buffer:
        writer = csv.DictWriter(buffer, header, restval="", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()


def write_if_changed(path: Path, text: str) -> bool:
    """Write a file only when its contents change, so unchanged files keep their time.

    Args:
        path: The file.
        text: Its new contents.

    Returns:
        Whether it was written.
    """
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def column_order(category: Category, headers: Iterable[Sequence[str]]) -> list[str]:
    """Order the columns of rows gathered from several files.

    Args:
        category: The category.
        headers: The headers the rows came with.

    Returns:
        The category's columns that appear, in the format's order, then any others
        in the order first seen.
    """
    seen = list(dict.fromkeys(name for header in headers for name in header))
    known = [name for name in category.columns if name in seen]
    return known + [name for name in seen if name not in category.columns]


def row_order(category: Category, row: Mapping[str, str]) -> tuple[str, ...]:
    """Sort key for a category's rows: date, then its other unique columns.

    Args:
        category: The category.
        row: A row's cells.

    Returns:
        The key.
    """
    rest = [name for name in category.key if name != "date"]
    return (row.get("date", ""), *(row.get(name, "") for name in rest))


@dataclass(frozen=True, slots=True)
class Staging:
    """Where a source script puts its rows, one folder per source.

    A script never writes the data files themselves: it writes
    ``<data>/sources/<source>/<file>``, and ``make fresh`` merges every source into
    the data files by the ranking in ``[sources]``.

    Attributes:
        config: The whole of config.toml.
        data_dir: The data folder.
    """

    config: Mapping[str, Any]
    data_dir: Path

    @property
    def timezone(self) -> ZoneInfo:
        """The person's time zone, for local dates."""
        return ZoneInfo(self.config["timezone"])

    def category(self, name: str) -> Category:
        """Find a category, custom metrics included.

        Args:
            name: Its name, e.g. ``sleep``.

        Returns:
            The category.

        Raises:
            ValueError: If there is no such category.
        """
        for category in all_categories(self.config):
            if category.name == name:
                return category
        raise ValueError(f"no category named {name!r}; see FORMAT.md")

    def wants(self, source: str, category: str) -> bool:
        """Tell whether a source should fill a category.

        Args:
            source: The source's name in ``[sources]``, e.g. ``apple-health``.
            category: The category's name.

        Returns:
            True when the category is switched on and ``[sources]`` lists the
            source for it.
        """
        spec = self.category(category)
        listed = self.config.get("sources", {}).get(category, ())
        return source in listed and context_for(spec, self.config).enabled

    def path(self, source: str, category: str) -> Path:
        """Return where a source's rows for a category go.

        Args:
            source: The source's name in ``[sources]``.
            category: The category's name.

        Returns:
            The staged file, or the staged folder for reflections.
        """
        return self.data_dir / SOURCES_DIR / source / self.category(category).file

    def write(
        self,
        source: str,
        category: str,
        rows: Iterable[Mapping[str, Cell]],
        window: tuple[date, date] | None = None,
    ) -> int:
        """Save a source's rows for one category, replacing what it wrote before.

        Running a script twice gives the same file: rows are sorted, and the whole
        file (or the window) is replaced, never appended to.

        Args:
            source: The source's name in ``[sources]``, e.g. ``apple-health``.
            category: The category's name, e.g. ``sleep``.
            rows: Values by column. ``source`` defaults to the source's name; set
                it per row for something finer, e.g. ``apple-watch``.
            window: First and last date fetched, both included, when the script
                re-fetches only recent days: rows outside it are kept. None
                replaces every row.

        Returns:
            How many rows were given.

        Raises:
            ValueError: For a column the category doesn't have, a row without a
                date, or a value the format can't hold.
        """
        spec = self.category(category)
        if spec.grain is Grain.ENTRY:
            raise ValueError(
                f"write {category} files into {self.path(source, category)}"
            )
        cells = [
            {name: cell_text(value) for name, value in row.items()} for row in rows
        ]
        for row in cells:
            row["source"] = row.get("source") or source
        if unknown := sorted(
            {name for row in cells for name in row} - set(spec.columns)
        ):
            raise ValueError(f"{category} has no column {', '.join(unknown)}")
        if any(not row.get("date") for row in cells):
            raise ValueError(f"every {category} row needs a date")
        path = self.path(source, category)
        header, kept = read_table(path)
        if window is None:
            kept = []
        else:
            first, last = (day.isoformat() for day in window)
            kept = [row for row in kept if not first <= row["date"] <= last]
        merged = sorted([*kept, *cells], key=lambda row: row_order(spec, row))
        columns = column_order(spec, [header, *(list(row) for row in cells)])
        write_if_changed(path, table_text(columns, merged))
        return len(cells)


def from_env() -> Staging:
    """Start a source script: read the settings ``make fresh`` passes it.

    Returns:
        The staging area for this run.

    Raises:
        RuntimeError: When the script isn't run by ``make fresh``.
    """
    config, data = os.environ.get(CONFIG_ENV), os.environ.get(DATA_ENV)
    if config is None or data is None:
        raise RuntimeError(
            "run source scripts with make fresh, or one with "
            "uv run dotlife fresh --only <name>"
        )
    return Staging(load_config(Path(config)), Path(data))


def ranked_by_date(
    tables: Sequence[tuple[str, Sequence[Mapping[str, str]]]],
) -> list[Mapping[str, str]]:
    """Keep, for each date, every row of the best source that has that date.

    Args:
        tables: (source, rows) pairs, best source first.

    Returns:
        The rows kept, in source order.

    Example:
        >>> watch = [{"date": "2026-03-02", "steps": "9120"}]
        >>> phone = [{"date": "2026-03-02", "steps": "8800"},
        ...          {"date": "2026-03-03", "steps": "4100"}]
        >>> kept = ranked_by_date([("watch", watch), ("phone", phone)])
        >>> [row["steps"] for row in kept]
        ['9120', '4100']
    """
    best: dict[str, str] = {}
    for source, rows in tables:
        for row in rows:
            best.setdefault(row.get("date", ""), source)
    return [
        row
        for source, rows in tables
        for row in rows
        if best[row.get("date", "")] == source
    ]


def left_out_values(
    tables: Sequence[tuple[str, Sequence[Mapping[str, str]]]],
    kept: Sequence[Mapping[str, str]],
) -> list[tuple[str, str, int]]:
    """Find values a lower-ranked source had that the kept rows of that date lack.

    Args:
        tables: (source, rows) pairs, best source first.
        kept: The rows ``ranked_by_date`` kept from them.

    Returns:
        (column, source, days) for each column a source had a value in on days
        its rows were left out and the kept rows had none.

    Example:
        >>> scale = [{"date": "2026-03-02", "weight_kg": "71.2", "waist_cm": ""}]
        >>> tape = [{"date": "2026-03-02", "weight_kg": "", "waist_cm": "80"}]
        >>> tables = [("scale", scale), ("manual", tape)]
        >>> left_out_values(tables, ranked_by_date(tables))
        [('waist_cm', 'manual', 1)]
    """
    filled: dict[str, set[str]] = defaultdict(set)
    for row in kept:
        filled[row.get("date", "")] |= {name for name, value in row.items() if value}
    kept_rows = {id(row) for row in kept}
    days: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source, rows in tables:
        for row in rows:
            if id(row) in kept_rows:
                continue
            day = row.get("date", "")
            for name, value in row.items():
                if value and name != "source" and name not in filled[day]:
                    days[name, source].add(day)
    return sorted((name, source, len(dates)) for (name, source), dates in days.items())


def entry_blocks(text: str, time_format: str) -> list[tuple[datetime, str]]:
    """Split a reflections file into entries, each kept exactly as written.

    Args:
        text: The file's contents.
        time_format: The ``strptime`` format of the times in brackets.

    Returns:
        (time, entry text) pairs; lines before the first entry are dropped.
    """
    blocks: list[tuple[datetime, list[str]]] = []
    for line in text.splitlines():
        header = header_time(line, time_format)
        if header is not None:
            blocks.append((header[0], [line]))
        elif blocks:
            blocks[-1][1].append(line)
    return [(time, "\n".join(lines).rstrip()) for time, lines in blocks]


def merge_reflections(
    category: Category,
    ranking: Sequence[str],
    root: Path,
    data_dir: Path,
    config: Mapping[str, Any],
) -> int:
    """Merge staged reflections files, per date, best source first.

    Args:
        category: The reflections category.
        ranking: Its sources, best first, that have staged files.
        root: The staging folder, ``<data>/sources``.
        data_dir: The data folder.
        config: The whole of config.toml.

    Returns:
        How many entries the merged files hold.
    """
    time_format, _ = settings(config.get(category.name, {}))
    tables = [
        (
            source,
            [
                {"date": f"{time:%Y-%m-%d}", "text": entry, "time": time.isoformat()}
                for path in sorted((root / source / category.file).glob("*.txt"))
                for time, entry in entry_blocks(
                    path.read_text(encoding="utf-8"), time_format
                )
            ],
        )
        for source in ranking
    ]
    kept = sorted(ranked_by_date(tables), key=lambda row: row["time"])
    by_year: dict[str, list[str]] = {}
    for row in kept:
        by_year.setdefault(row["date"][:4], []).append(row["text"])
    for year, entries in by_year.items():
        write_if_changed(
            data_dir / category.file / f"{year}.txt", "\n\n".join(entries) + "\n"
        )
    return len(kept)


def merge(data_dir: Path, config: Mapping[str, Any]) -> list[str]:
    """Build the data files from every source's staged rows.

    For each date, a file keeps the rows of the best source in ``[sources]`` that
    has that date, so a lower-ranked source only fills days the better ones miss.
    Transactions and life events, whose rows can repeat, keep every source's
    rows. A data file no source has staged rows for is left as it is.

    Args:
        data_dir: The data folder.
        config: The whole of config.toml.

    Returns:
        A line per data file built, one per staged folder left out, and one per
        column whose values a higher-ranked source's rows replaced with nothing.
    """
    root = data_dir / SOURCES_DIR
    if not root.is_dir():
        return []
    staged = sorted(path.name for path in root.iterdir() if path.is_dir())
    lines = []
    for category in all_categories(config):
        present = [
            source for source in staged if (root / source / category.file).exists()
        ]
        if not present:
            continue
        listed = config.get("sources", {}).get(category.name, [])
        ranking = [source for source in listed if source in present]
        enabled = context_for(category, config).enabled
        left_out = present if not enabled else [s for s in present if s not in listed]
        if left_out:
            reason = (
                "it is switched off" if not enabled else "[sources] doesn't list it"
            )
            lines.append(
                f"{category.file}: left out {', '.join(left_out)}, because {reason}"
            )
        if not enabled or not ranking:
            continue
        if category.grain is Grain.ENTRY:
            count = merge_reflections(category, ranking, root, data_dir, config)
            noun = "entry", "entries"
        else:
            tables = [
                (source, read_table(root / source / category.file))
                for source in ranking
            ]
            rows = [(source, rows) for source, (_, rows) in tables]
            kept = (
                ranked_by_date(rows)
                if category.key
                else [row for _, source_rows in rows for row in source_rows]
            )
            lines += [
                f"{category.file}: {column} from {source} left out on "
                f"{plural(days, 'day')}, when a higher-ranked source had the day"
                for column, source, days in left_out_values(rows, kept)
            ]
            kept.sort(key=lambda row: row_order(category, row))
            columns = column_order(category, [header for _, (header, _) in tables])
            write_if_changed(data_dir / category.file, table_text(columns, kept))
            count, noun = len(kept), ("row", "rows")
        lines.append(
            f"{category.file}: {plural(count, *noun)} from {', '.join(ranking)}"
        )
    return lines
