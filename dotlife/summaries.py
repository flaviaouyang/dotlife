import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any, cast
from zoneinfo import ZoneInfo

from dotlife.periods import Period, minutes_after_evening, period_start
from dotlife.schema import Aggregate, Category, Context, Row

POUNDS_PER_KG = 2.2046226218
MG_DL_PER_MMOL_L = 18.0182
CONVERSIONS: dict[str, tuple[str, dict[str, float]]] = {
    "kg": ("weight", {"lb": POUNDS_PER_KG}),
    "mmol/L": ("glucose", {"mg/dL": MG_DL_PER_MMOL_L}),
}

Daily = dict[date, float]
RowFilter = Callable[[Row], bool]


class Status(StrEnum):
    """Where a value sits against its usual range."""

    BELOW = "below"
    USUAL = "usual"
    ABOVE = "above"


class Tone(StrEnum):
    """Whether a value's position is good, bad, or neither, for its metric."""

    GOOD = "good"
    BAD = "bad"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class UsualRange:
    """The middle half of recent full periods: "normal for you lately".

    Attributes:
        low: The first quartile.
        median: The median.
        high: The third quartile.
        periods: How many periods it was computed from.
    """

    low: float
    median: float
    high: float
    periods: int

    @property
    def width(self) -> float:
        """The range's width, never zero, so distances outside it stay finite."""
        return (self.high - self.low) or abs(self.median) or 1.0


@dataclass(frozen=True, slots=True)
class Assessment:
    """A period's value judged against its usual range.

    Attributes:
        status: Below, within, or above the range.
        tone: Good, bad or neutral, from the metric's better direction.
        distance: How many range widths outside the range it is; 0 inside it.
    """

    status: Status
    tone: Tone
    distance: float


def daily_values(
    category: Category,
    rows: Iterable[Row],
    column: str,
    context: Context,
    where: RowFilter | None = None,
) -> Daily:
    """Total a metric per date, across sessions or items on the same date.

    Rows the category's day filter rejects (e.g. watch-off days) are left out, so
    they don't count toward averages. Missing values are skipped, never zero.

    Args:
        category: The category the rows belong to.
        rows: Its parsed rows.
        column: The metric's column.
        context: Settings for the category's day filter.
        where: An optional extra row filter, e.g. one habit or one currency.

    Returns:
        Each date with at least one value, and that date's total.
    """
    totals: Daily = defaultdict(float)
    for row in rows:
        if where is not None and not where(row):
            continue
        if category.day_filter is not None and not category.day_filter(row, context):
            continue
        value = row.get(column)
        if value is not None:
            totals[cast(date, row["date"])] += cast(float, value)
    return dict(totals)


def daily_counts(rows: Iterable[Row], where: RowFilter | None = None) -> Daily:
    """Count rows per date, e.g. workouts per day.

    Args:
        rows: Parsed rows with a ``date``.
        where: An optional row filter.

    Returns:
        Each date with rows, and how many.
    """
    counts = Counter(
        cast(date, row["date"]) for row in rows if where is None or where(row)
    )
    return {day: float(count) for day, count in counts.items()}


def clock_by_day(rows: Iterable[Row], column: str, timezone: ZoneInfo) -> Daily:
    """Return each date's main session clock time, as minutes after 18:00.

    The main session is the longest one filed under that date, so a nap doesn't
    move the bedtime.

    Args:
        rows: Parsed session rows with ``date``, ``start`` and ``end``.
        column: ``start`` for bedtimes, ``end`` for wake times.
        timezone: The user's time zone.

    Returns:
        Each date with a session, and its clock time in minutes after 18:00.
    """
    longest: dict[date, Row] = {}
    for row in rows:
        day = cast(date, row["date"])
        if day not in longest or duration(row) > duration(longest[day]):
            longest[day] = row
    return {
        day: float(
            minutes_after_evening(
                cast(datetime, row[column]).astimezone(timezone).time()
            )
        )
        for day, row in longest.items()
    }


def duration(row: Row) -> timedelta:
    """Return how long a session lasted.

    Args:
        row: A parsed row with ``start`` and ``end`` timestamps.

    Returns:
        The real elapsed time, correct across DST changes.
    """
    return cast(datetime, row["end"]) - cast(datetime, row["start"])


SUMMARIES: dict[Aggregate, Callable[[Sequence[float]], float]] = {
    Aggregate.SUM: math.fsum,
    Aggregate.MEAN: statistics.fmean,
    Aggregate.LAST: lambda values: values[-1],
    Aggregate.DAYS: lambda values: float(sum(value > 0 for value in values)),
}


def period_values(
    daily: Mapping[date, float], aggregate: Aggregate, period: Period
) -> Daily:
    """Summarise daily values into one value per week or month.

    Args:
        daily: Values by date.
        aggregate: How a period's daily values combine.
        period: Weeks (Monday to Sunday) or calendar months.

    Returns:
        Each period that has values, keyed by its first day.

    Example:
        >>> daily = {date(2026, 3, 2): 4.0, date(2026, 3, 3): 6.0,
        ...          date(2026, 3, 9): 1.0}
        >>> period_values(daily, Aggregate.MEAN, Period.WEEK)
        {datetime.date(2026, 3, 2): 5.0, datetime.date(2026, 3, 9): 1.0}
    """
    buckets: dict[date, list[float]] = defaultdict(list)
    for day in sorted(daily):
        buckets[period_start(day, period)].append(daily[day])
    return {start: SUMMARIES[aggregate](values) for start, values in buckets.items()}


def previous_starts(current: date, period: Period, count: int) -> list[date]:
    """List the first days of the periods just before a period.

    Args:
        current: The first day of the current period.
        period: Weeks or months.
        count: How many periods to go back.

    Returns:
        The earlier periods' first days, most recent first.
    """
    starts = []
    start = current
    for _ in range(count):
        start = period_start(start - timedelta(days=1), period)
        starts.append(start)
    return starts


def usual_range(
    values: Mapping[date, float],
    current: date,
    period: Period,
    count: int,
    minimum: int = 3,
) -> UsualRange | None:
    """Work out the usual range from the full periods just before the current one.

    Args:
        values: Period values keyed by first day, from ``period_values``.
        current: The first day of the period being judged; it is left out.
        period: Weeks or months.
        count: How many earlier periods to look at (e.g. 8 weeks).
        minimum: Fewest periods with data needed; fewer gives None.

    Returns:
        The range, or None when there isn't enough history.

    Example:
        >>> weeks = {date(2026, 3, 2) + timedelta(weeks=i): float(i) for i in range(9)}
        >>> usual_range(weeks, date(2026, 4, 27), Period.WEEK, 8)
        UsualRange(low=1.75, median=3.5, high=5.25, periods=8)
    """
    history = [
        values[start]
        for start in previous_starts(current, period, count)
        if start in values
    ]
    if len(history) < minimum:
        return None
    low, median, high = statistics.quantiles(history, n=4, method="inclusive")
    return UsualRange(low, median, high, len(history))


def assess(
    value: float, usual: UsualRange, higher_is_better: bool | None
) -> Assessment:
    """Judge a value against its usual range.

    Args:
        value: The period's value.
        usual: The usual range.
        higher_is_better: The metric's good direction, or None when neither is.

    Returns:
        Its status, tone and distance outside the range.
    """
    if usual.low <= value <= usual.high:
        return Assessment(Status.USUAL, Tone.NEUTRAL, 0.0)
    above = value > usual.high
    distance = (value - usual.high if above else usual.low - value) / usual.width
    status = Status.ABOVE if above else Status.BELOW
    if higher_is_better is None:
        return Assessment(status, Tone.NEUTRAL, distance)
    tone = Tone.GOOD if above is higher_is_better else Tone.BAD
    return Assessment(status, tone, distance)


def notable(assessments: Mapping[str, Assessment], limit: int) -> list[str]:
    """Pick the metrics furthest outside their usual range, good or bad.

    Neutral metrics (no better direction) are left out.

    Args:
        assessments: Assessments by metric name.
        limit: How many to return at most.

    Returns:
        Metric names, furthest outside first.
    """
    ranked = sorted(
        (
            (assessment.distance, name)
            for name, assessment in assessments.items()
            if assessment.tone is not Tone.NEUTRAL
        ),
        reverse=True,
    )
    return [name for _, name in ranked[:limit]]


def last_change(daily: Mapping[date, float]) -> date | None:
    """Return the date a metric's most recent value first appeared.

    Args:
        daily: Values by date.

    Returns:
        The first date of the final run of equal values, or None without values.

    Example:
        >>> last_change({date(2026, 1, 1): 40.0, date(2026, 2, 1): 41.0,
        ...              date(2026, 3, 1): 41.0})
        datetime.date(2026, 2, 1)
    """
    if not daily:
        return None
    days = sorted(daily, reverse=True)
    latest = daily[days[0]]
    changed = days[0]
    for day in days:
        if daily[day] != latest:
            break
        changed = day
    return changed


def stuck_against(
    daily: Mapping[date, float], related: Mapping[str, Assessment], since: date
) -> tuple[str, ...]:
    """Name the related metrics that moved while this one stayed flat.

    A metric is stuck when its value hasn't changed since ``since`` (the start of
    the usual-range window) while a related metric left its usual range. That
    hints at a source that stopped updating; it is flagged, never corrected.

    Args:
        daily: The metric's values by date.
        related: Current assessments of its related metrics, by name.
        since: The start of the window it should have changed in.

    Returns:
        The related metrics that moved, or nothing when it isn't stuck.
    """
    changed = last_change(daily)
    if changed is None or changed >= since:
        return ()
    return tuple(
        name
        for name, assessment in related.items()
        if assessment.status is not Status.USUAL
    )


def display_value(
    value: float, unit: str, display: Mapping[str, Any]
) -> tuple[float, str]:
    """Convert a stored metric value to the unit chosen in ``[display]``.

    Files always store metric units; only kilograms and mmol/L have alternatives.

    Args:
        value: The stored value.
        unit: Its stored unit, e.g. ``kg``.
        display: The ``[display]`` section of config.toml.

    Returns:
        The value and unit to show.

    Raises:
        ValueError: If ``[display]`` asks for a unit dotlife can't convert to.

    Example:
        >>> value, unit = display_value(70.0, "kg", {"weight": "lb"})
        >>> round(value, 1), unit
        (154.3, 'lb')
    """
    if unit not in CONVERSIONS:
        return value, unit
    setting, factors = CONVERSIONS[unit]
    wanted = display.get(setting, unit)
    if wanted == unit:
        return value, unit
    if wanted not in factors:
        choices = ", ".join([unit, *factors])
        raise ValueError(f"config.toml: [display] {setting} must be one of {choices}")
    return value * factors[wanted], wanted
