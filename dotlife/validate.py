import csv
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from dotlife.config import all_categories, context_for, plausible_range
from dotlife.schema import (
    FORMAT_VERSION,
    Category,
    Context,
    Grain,
    Metric,
    Row,
    row_parser,
)

JOURNAL_FILE = re.compile(r"(\d{4}-\d{2}-\d{2})\.md")


class Severity(StrEnum):
    """How serious a problem is. Errors fail validation; warnings don't."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Problem:
    """Something wrong or odd in a data file or the config.

    Attributes:
        severity: Error or warning.
        message: What is wrong, in plain words.
        line: Line number in the file, when the problem is on one row.
        column: Column name, when the problem is in one cell.
    """

    severity: Severity
    message: str
    line: int | None = None
    column: str | None = None


@dataclass(slots=True)
class FileReport:
    """What validating one category's data found.

    Attributes:
        category: The category's name.
        path: The file or folder that was read.
        rows: Number of rows or entries read.
        noun: What a row is called in the text report, e.g. "entry"; plural adds "s"
            unless it ends in "y", which becomes "ies".
        first_date: Earliest date seen, or None if there were no valid rows.
        last_date: Latest date seen, or None if there were no valid rows.
        gaps: Missing date ranges, inclusive, for categories expected every day.
        days_skipped: Days left out of averages by the category's day filter.
        problems: Errors and warnings, in file order.
        last_changes: Per metric with a stale threshold, the date its latest value
            first appeared.
    """

    category: str
    path: str
    rows: int = 0
    noun: str = "row"
    first_date: date | None = None
    last_date: date | None = None
    gaps: list[tuple[date, date]] = field(default_factory=list)
    days_skipped: int = 0
    problems: list[Problem] = field(default_factory=list)
    last_changes: dict[str, date] = field(default_factory=dict)


@dataclass(slots=True)
class Report:
    """What validating a whole data folder found.

    Attributes:
        data_dir: The folder that was validated.
        files: One report per category with data.
        missing: Enabled categories without a data file; they won't show.
        disabled: Categories switched off in config.toml; not read.
        problems: Problems with the config rather than a data file.
    """

    data_dir: str
    files: list[FileReport] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def as_of(self) -> date | None:
        """The latest date in any file, which staleness is measured against."""
        return max(
            (report.last_date for report in self.files if report.last_date),
            default=None,
        )

    @property
    def all_problems(self) -> list[Problem]:
        """Every problem: the config's first, then each file's."""
        return self.problems + [
            problem for report in self.files for problem in report.problems
        ]

    @property
    def error_count(self) -> int:
        """Number of errors across the config and all files."""
        return sum(problem.severity is Severity.ERROR for problem in self.all_problems)

    @property
    def warning_count(self) -> int:
        """Number of warnings across the config and all files."""
        return sum(
            problem.severity is Severity.WARNING for problem in self.all_problems
        )


def header_problems(category: Category, header: list[str]) -> list[Problem]:
    """Check a CSV header: required columns present, no unknown or repeated ones.

    Args:
        category: The category the file belongs to.
        header: Column names from the file's first line.

    Returns:
        Errors for missing required or repeated columns; warnings for unknown ones.
    """
    known = set(category.columns)
    required = [field.name for field in category.fields if field.required]
    problems = [
        Problem(Severity.ERROR, "required column is missing", column=name)
        for name in required
        if name not in header
    ]
    problems += [
        Problem(Severity.ERROR, "column appears more than once", column=name)
        for name in sorted({name for name in header if header.count(name) > 1})
    ]
    problems += [
        Problem(Severity.WARNING, "unknown column; it is ignored", column=name)
        for name in header
        if name not in known
    ]
    return problems


def value_problem(
    metric: Metric, value: float, plausible: tuple[float, float] | None
) -> Problem | None:
    """Check one number against its metric's hard limits, then its plausible bounds.

    Args:
        metric: The metric the value belongs to.
        value: The parsed value.
        plausible: The plausible bounds in force, or None.

    Returns:
        An error for an impossible value, a warning for an unlikely one, else None.
    """
    if metric.minimum is not None and value < metric.minimum:
        return Problem(
            Severity.ERROR,
            f"{value:g} is below the minimum {metric.minimum:g}",
            column=metric.column,
        )
    if metric.maximum is not None and value > metric.maximum:
        return Problem(
            Severity.ERROR,
            f"{value:g} is above the maximum {metric.maximum:g}",
            column=metric.column,
        )
    if plausible is None or plausible[0] <= value <= plausible[1]:
        return None
    return Problem(
        Severity.WARNING,
        f"{value:,g} is outside the usual {plausible[0]:,g} to {plausible[1]:,g}; "
        "check it, or widen the bounds in config.toml",
        column=metric.column,
    )


def row_problems(
    category: Category,
    row: Row,
    bounds: Mapping[str, tuple[Metric, tuple[float, float] | None]],
    context: Context,
) -> list[Problem]:
    """Check one parsed row: every value, then the category's own rules.

    Args:
        category: The category the row belongs to.
        row: The parsed row.
        bounds: For each metric column in the file, the metric and its plausible
            bounds in force.
        context: Settings for the category's plug-ins.

    Returns:
        The row's problems, without line numbers.
    """
    problems = [
        problem
        for column, (metric, plausible) in bounds.items()
        if (value := row.get(column)) is not None
        and (problem := value_problem(metric, cast(float, value), plausible))
        is not None
    ]
    problems += [
        Problem(Severity.ERROR, message)
        for check in category.checks
        if (message := check(row, context)) is not None
    ]
    problems += [
        Problem(Severity.WARNING, message)
        for check in category.warnings
        if (message := check(row, context)) is not None
    ]
    return problems


def find_gaps(dates: set[date]) -> list[tuple[date, date]]:
    """Find runs of missing days between the first and last date.

    Args:
        dates: Days that have data.

    Returns:
        Inclusive (first missing, last missing) ranges, in order.

    Example:
        >>> days = {date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 5)}
        >>> find_gaps(days)
        [(datetime.date(2026, 1, 3), datetime.date(2026, 1, 4))]
    """
    ordered = sorted(dates)
    return [
        (before + timedelta(days=1), after - timedelta(days=1))
        for before, after in zip(ordered, ordered[1:], strict=False)
        if (after - before).days > 1
    ]


def last_change_dates(
    readings: Mapping[str, list[tuple[date, float]]],
) -> dict[str, date]:
    """Find, per metric, the date its most recent value first appeared.

    Args:
        readings: Per metric, (date, value) pairs in any order.

    Returns:
        Per metric with readings, the first date of its final run of equal values.

    Example:
        >>> readings = {"vo2": [(date(2026, 1, 1), 40.0), (date(2026, 2, 1), 41.0),
        ...                     (date(2026, 3, 1), 41.0)]}
        >>> last_change_dates(readings)
        {'vo2': datetime.date(2026, 2, 1)}
    """
    changes = {}
    for column, pairs in readings.items():
        if not pairs:
            continue
        ordered = sorted(pairs)
        latest = ordered[-1][1]
        changed = ordered[-1][0]
        for day, value in reversed(ordered):
            if value != latest:
                break
            changed = day
        changes[column] = changed
    return changes


def duplicate_problem(
    category: Category, row: Row, line: int, seen_keys: dict[tuple, int]
) -> Problem | None:
    """Check that a row's key hasn't been seen before, and remember it.

    Args:
        category: The category, whose ``key`` columns must be unique.
        row: The parsed row.
        line: The row's line number.
        seen_keys: Lines of keys seen so far; updated with this row's key.

    Returns:
        An error pointing at the first occurrence, or None.
    """
    if not category.key:
        return None
    key = tuple(row[name] for name in category.key)
    first_line = seen_keys.setdefault(key, line)
    if first_line == line:
        return None
    return Problem(
        Severity.ERROR,
        f"duplicate of line {first_line} ({', '.join(category.key)} must be unique)",
        line,
    )


def validate_csv(category: Category, path: Path, context: Context) -> FileReport:
    """Validate one category's CSV file.

    Args:
        category: The category.
        path: Its data file.
        context: Settings for the category.

    Returns:
        What was found. Rows that fail to parse are reported and skipped.

    Raises:
        ValueError: If config.toml overrides a plausible bound wrongly.
    """
    report = FileReport(category.name, str(path))
    stale_after = context.options.get("stale_after_days", {})
    readings: dict[str, list[tuple[date, float]]] = {
        column: [] for column in stale_after
    }
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        header = list(reader.fieldnames or [])
        report.problems += header_problems(category, header)
        if any(problem.severity is Severity.ERROR for problem in report.problems):
            return report
        parse = row_parser(category)
        bounds = {
            metric.column: (metric, plausible_range(metric, context))
            for metric in category.metrics
            if metric.column in header
        }
        seen_keys: dict[tuple, int] = {}
        dates: set[date] = set()
        for raw in reader:
            line = reader.line_num
            report.rows += 1
            try:
                row = parse(raw)
            except ValueError as error:
                report.problems.append(Problem(Severity.ERROR, str(error), line))
                continue
            report.problems += [
                Problem(problem.severity, problem.message, line, problem.column)
                for problem in row_problems(category, row, bounds, context)
            ]
            if (
                duplicate := duplicate_problem(category, row, line, seen_keys)
            ) is not None:
                report.problems.append(duplicate)
            day = cast(date, row["date"])
            dates.add(day)
            if category.day_filter is not None and not category.day_filter(
                row, context
            ):
                report.days_skipped += 1
            for column, pairs in readings.items():
                if (value := row.get(column)) is not None:
                    pairs.append((day, cast(float, value)))
    if dates:
        report.first_date, report.last_date = min(dates), max(dates)
    if category.expect_every_day:
        report.gaps = find_gaps(dates)
    report.last_changes = last_change_dates(readings)
    return report


def journal_date(name: str) -> date | None:
    """Return the date a journal file is named after.

    Args:
        name: A file name, e.g. ``2026-03-08.md``.

    Returns:
        The date, or None when the name isn't a real ``YYYY-MM-DD.md`` date.
    """
    match = JOURNAL_FILE.fullmatch(name)
    if match is None:
        return None
    try:
        return date.fromisoformat(match[1])
    except ValueError:
        return None


def validate_journal(category: Category, folder: Path) -> FileReport:
    """Validate a folder of daily Markdown files named ``YYYY-MM-DD.md``.

    Args:
        category: The journal category.
        folder: The journal folder.

    Returns:
        What was found: one row per valid entry, warnings for misnamed files.
    """
    report = FileReport(category.name, str(folder), noun="entry")
    dates: set[date] = set()
    for path in sorted(folder.iterdir()):
        day = journal_date(path.name)
        if day is None:
            report.problems.append(
                Problem(
                    Severity.WARNING,
                    f"{path.name} is not named YYYY-MM-DD.md; it is ignored",
                )
            )
            continue
        dates.add(day)
    report.rows = len(dates)
    if dates:
        report.first_date, report.last_date = min(dates), max(dates)
    return report


def stale_problems(report: FileReport, context: Context, as_of: date) -> list[Problem]:
    """Warn about metrics whose value hasn't changed for longer than allowed.

    Args:
        report: The category's report, with ``last_changes`` filled in.
        context: Supplies ``stale_after_days`` per column.
        as_of: The date staleness is measured against: the latest date in the data.

    Returns:
        One warning per stale metric.
    """
    stale_after = context.options.get("stale_after_days", {})
    return [
        Problem(
            Severity.WARNING,
            f"unchanged since {changed} ({(as_of - changed).days} days); "
            "it may be stale, so it is left out of trends",
            column=column,
        )
        for column, changed in report.last_changes.items()
        if (as_of - changed).days >= stale_after[column]
    ]


def data_path(category: Category, data_dir: Path) -> Path:
    """Return where a category's data lives.

    Args:
        category: The category.
        data_dir: The data folder.

    Returns:
        The file, or for the journal the folder.
    """
    return data_dir / category.file.rstrip("/")


def validate_folder(data_dir: Path, config: Mapping[str, Any]) -> Report:
    """Validate every enabled category's data in a folder.

    Args:
        data_dir: The data folder.
        config: The whole of config.toml.

    Returns:
        The report. Config mistakes are reported as errors, not raised.
    """
    report = Report(str(data_dir))
    version = config.get("format_version")
    if version != FORMAT_VERSION:
        report.problems.append(
            Problem(
                Severity.ERROR,
                f"config.toml: format_version is {version!r}; this dotlife reads "
                f"version {FORMAT_VERSION}",
            )
        )
    try:
        categories = all_categories(config)
        contexts = {
            category.name: context_for(category, config) for category in categories
        }
    except ValueError as error:
        report.problems.append(Problem(Severity.ERROR, str(error)))
        return report
    for category in categories:
        context = contexts[category.name]
        path = data_path(category, data_dir)
        if not context.enabled:
            report.disabled.append(category.name)
        elif not path.exists():
            report.missing.append(category.name)
        elif category.grain is Grain.ENTRY:
            report.files.append(validate_journal(category, path))
        else:
            try:
                report.files.append(validate_csv(category, path, context))
            except ValueError as error:
                report.problems.append(Problem(Severity.ERROR, str(error)))
    as_of = report.as_of
    if as_of is not None:
        for file_report in report.files:
            file_report.problems += stale_problems(
                file_report, contexts[file_report.category], as_of
            )
    return report


def plural(count: int, noun: str, plural_noun: str | None = None) -> str:
    """Format a count with its noun, singular only for exactly one.

    Args:
        count: How many.
        noun: The singular noun.
        plural_noun: The plural, when it isn't ``noun`` plus "s".

    Returns:
        E.g. ``1 error``, ``3 errors`` or ``2 categories``.
    """
    if count == 1:
        return f"{count} {noun}"
    return f"{count} {plural_noun or noun + 's'}"


def problem_line(problem: Problem) -> str:
    """Render one problem as an indented line, with its location if it has one.

    Args:
        problem: The problem.

    Returns:
        E.g. ``  error    line 14, steps: -5 is below the minimum 0``.
    """
    where = ", ".join(
        part
        for part in (
            None if problem.line is None else f"line {problem.line}",
            problem.column,
        )
        if part is not None
    )
    prefix = f"{where}: " if where else ""
    return f"  {problem.severity:<8} {prefix}{problem.message}"


def file_lines(report: FileReport) -> list[str]:
    """Render one file's findings.

    Args:
        report: The file's report.

    Returns:
        A heading line with the row count and date span, then one line per finding.
    """
    span = (
        f", {report.first_date} to {report.last_date}"
        if report.first_date is not None
        else ""
    )
    nouns = f"{report.noun[:-1]}ies" if report.noun.endswith("y") else None
    count = plural(report.rows, report.noun, nouns)
    lines = [f"{Path(report.path).name}: {count}{span}"]
    lines += [problem_line(problem) for problem in report.problems]
    lines += [
        f"  gap      {start} to {end} ({plural((end - start).days + 1, 'day')} missing)"
        for start, end in report.gaps
    ]
    if report.days_skipped:
        lines.append(
            f"  skipped  {plural(report.days_skipped, 'day')} left out of averages"
        )
    return lines


def format_text(report: Report) -> str:
    """Render a report for people.

    Args:
        report: The validation report.

    Returns:
        Plain text: config problems, each file's findings, then a summary line.
    """
    as_of = "" if report.as_of is None else f" (data up to {report.as_of})"
    lines = [f"Validated {report.data_dir}{as_of}"]
    lines += [problem_line(problem) for problem in report.problems]
    for file_report in report.files:
        lines += ["", *file_lines(file_report)]
    if report.missing:
        lines += ["", f"No data, so not shown: {', '.join(report.missing)}"]
    if report.disabled:
        lines += ["", f"Switched off in config.toml: {', '.join(report.disabled)}"]
    lines += [
        "",
        f"{plural(report.error_count, 'error')}, "
        f"{plural(report.warning_count, 'warning')} "
        f"in {plural(len(report.files), 'category', 'categories')}.",
    ]
    return "\n".join(lines)


def format_json(report: Report) -> str:
    """Render a report for programs, such as the dashboard and the sync skill.

    Args:
        report: The validation report.

    Returns:
        JSON with every field of the report plus ``as_of`` and the counts.
    """
    data = asdict(report) | {
        "as_of": report.as_of,
        "error_count": report.error_count,
        "warning_count": report.warning_count,
    }
    return json.dumps(data, default=str, indent=2)
