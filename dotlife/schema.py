import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

Value = date | datetime | float | str | None
Row = dict[str, Value]


class Kind(StrEnum):
    """How a non-numeric column is parsed."""

    DATE = "date"
    TIMESTAMP = "timestamp"
    TEXT = "text"


class Grain(StrEnum):
    """What one row of a category's file stands for."""

    DAY = "day"
    SESSION = "session"


class Aggregate(StrEnum):
    """How a metric's daily values sum up over a week or month."""

    SUM = "sum"
    MEAN = "mean"
    LAST = "last"
    DAYS = "days"


@dataclass(frozen=True, slots=True)
class Field:
    """A non-numeric column.

    Attributes:
        name: Column name in the file.
        kind: How values are parsed.
        required: Whether every row needs a value.
    """

    name: str
    kind: Kind
    required: bool = True


DATE = Field("date", Kind.DATE)
START = Field("start", Kind.TIMESTAMP)
END = Field("end", Kind.TIMESTAMP)
SOURCE = Field("source", Kind.TEXT)


@dataclass(frozen=True, slots=True)
class Metric:
    """A numeric column. An empty cell means the value is missing.

    Attributes:
        column: Column name, ending in its unit (e.g. ``asleep_min``).
        label: Name shown in the dashboard.
        unit: Unit shown in the dashboard.
        minimum: Lowest valid value; anything lower is an error in the file.
        maximum: Highest valid value; anything higher is an error in the file.
        aggregate: How daily values sum up over a period.
        higher_is_better: True or False when one direction is good, None when
            neither is.
    """

    column: str
    label: str
    unit: str
    minimum: float
    maximum: float
    aggregate: Aggregate
    higher_is_better: bool | None = None


@dataclass(frozen=True, slots=True)
class Context:
    """The settings a category's plug-ins need from config.toml.

    Attributes:
        timezone: The user's local time zone.
        options: The category's own section of config.toml.
    """

    timezone: ZoneInfo
    options: Mapping[str, Any]

    @property
    def enabled(self) -> bool:
        """Whether the category is switched on; on unless config says otherwise."""
        return self.options.get("enabled", True)


Check = Callable[[Row, Context], str | None]
DayFilter = Callable[[Row, Context], bool]


@dataclass(frozen=True, slots=True)
class Category:
    """One kind of data, stored in one file, with optional plug-ins for special rules.

    Attributes:
        name: Identifier, also the name of its section in config.toml.
        label: Name shown in the dashboard.
        file: File name inside the data folder.
        grain: What one row stands for.
        fields: Non-numeric columns, in file order.
        metrics: Numeric columns, in file order after the fields.
        key: Columns whose values must be unique across rows.
        sensitive: Whether the dashboard hides it until "Show sensitive" is on.
        checks: Extra row checks; each returns a problem description or None.
        day_filter: Decides which days count toward averages, e.g. leaving out
            watch-off days.
    """

    name: str
    label: str
    file: str
    grain: Grain
    fields: tuple[Field, ...]
    metrics: tuple[Metric, ...]
    key: tuple[str, ...] = ("date",)
    sensitive: bool = False
    checks: tuple[Check, ...] = ()
    day_filter: DayFilter | None = None

    @property
    def columns(self) -> tuple[str, ...]:
        """All column names, in file order."""
        return tuple(field.name for field in self.fields) + tuple(
            metric.column for metric in self.metrics
        )


def parse_timestamp(text: str) -> datetime:
    """Parse an ISO 8601 timestamp that includes its UTC offset.

    Args:
        text: E.g. ``2026-03-08T07:30-04:00``.

    Returns:
        A timezone-aware datetime.

    Raises:
        ValueError: If the text isn't ISO 8601 or has no UTC offset.
    """
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError(
            f"{text!r} has no UTC offset; write it like 2026-03-08T07:30-04:00"
        )
    return moment


def parse_number(text: str) -> float:
    """Parse a finite number.

    Args:
        text: E.g. ``8421`` or ``71.5``.

    Returns:
        The number.

    Raises:
        ValueError: If the text isn't a number, or is NaN or infinite.
    """
    number = float(text)
    if not math.isfinite(number):
        raise ValueError(f"{text!r} is not a finite number")
    return number


PARSERS: dict[Kind, Callable[[str], Value]] = {
    Kind.DATE: date.fromisoformat,
    Kind.TIMESTAMP: parse_timestamp,
    Kind.TEXT: str,
}


def parse_cell(
    name: str, text: str | None, parser: Callable[[str], Value], required: bool
) -> Value:
    """Parse one cell, treating an empty cell as missing.

    Args:
        name: Column name, used in error messages.
        text: The raw cell, or None when the row has no such column.
        parser: Converts non-empty text to a value.
        required: Whether an empty cell is an error.

    Returns:
        The parsed value, or None for an empty optional cell.

    Raises:
        ValueError: If the cell is empty but required, or can't be parsed.
    """
    text = (text or "").strip()
    if not text:
        if required:
            raise ValueError(f"{name}: a value is required")
        return None
    try:
        return parser(text)
    except ValueError as error:
        raise ValueError(f"{name}: {error}") from error


def row_parser(category: Category) -> Callable[[Mapping[str, str]], Row]:
    """Build a parser for one category's CSV rows, set up once per file.

    Args:
        category: The category whose rows will be parsed.

    Returns:
        A function from a raw row (as read by ``csv.DictReader``) to typed values. It
        raises ValueError, naming the column, for an empty required cell or bad value.

    Example:
        >>> from dotlife.categories import MOOD
        >>> parse = row_parser(MOOD)
        >>> parse({"date": "2026-01-05", "source": "manual", "mood": "4"})["mood"]
        4.0
    """
    cells = [
        (field.name, PARSERS[field.kind], field.required) for field in category.fields
    ] + [(metric.column, parse_number, False) for metric in category.metrics]

    def parse(raw: Mapping[str, str]) -> Row:
        return {
            name: parse_cell(name, raw.get(name), parser, required)
            for name, parser, required in cells
        }

    return parse
