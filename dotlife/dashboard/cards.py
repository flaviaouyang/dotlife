from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from enum import StrEnum
from typing import Any, cast

from dotlife.config import Goal, goal_for
from dotlife.dashboard.display import (
    AREA_OF,
    AREAS,
    CLOCK,
    SCALE_UNITS,
    TONE_COLORS,
    CardSpec,
    Color,
    format_delta,
    format_value,
    unit_label,
)
from dotlife.load import Dataset
from dotlife.periods import Period, period_end
from dotlife.schema import Aggregate, Category, Grain, Row
from dotlife.summaries import (
    Assessment,
    Daily,
    Status,
    UsualRange,
    assess,
    budget_shares,
    clock_by_day,
    cycle_status,
    daily_counts,
    daily_values,
    display_value,
    last_change,
    notable,
    period_values,
    previous_starts,
    stuck_against,
    usual_range,
)

SERIES_LENGTH = 26
CYCLE_WINDOW_DAYS = 56
NOTABLE_LIMIT = 4
DEFAULT_USUAL_PERIODS = {Period.WEEK: 8, Period.MONTH: 6}
OVERVIEW_COLUMNS = {
    "activity": ("steps", "active_min"),
    "sleep": ("asleep_min",),
    "heart": ("resting_hr_bpm", "hrv_ms"),
    "body": ("weight_kg",),
    "vitals": ("spo2_pct",),
    "mood": ("mood", "energy", "stress"),
    "reading": ("pages",),
    "learning": ("learning_min",),
    "media": ("listening_min",),
}
LABELS = {
    "habits.times": "Habit check-ins",
    "cycle.flow_level": "Menstrual cycle",
    "time.hours": "Time tracked",
    "medication.doses": "Medication doses",
    "symptoms.severity": "Symptom severity",
    "travel.travel_day": "Travel days",
}
AGGREGATE_OVERRIDES = {"habits.times": Aggregate.SUM}
UNITLESS = ("min", CLOCK, "")
STATUS_CHIPS = {
    Status.BELOW: "Below usual",
    Status.USUAL: "Usual",
    Status.ABOVE: "Above usual",
}
COMPARABLE_WHILE_PARTIAL = (Aggregate.MEAN, Aggregate.LAST)


@dataclass(frozen=True, slots=True)
class Selection:
    """What the sidebar has chosen; every page reads it.

    Attributes:
        period: Weeks or months.
        start: First day of the chosen period.
        show_sensitive: Whether sensitive categories are shown.
    """

    period: Period
    start: date
    show_sensitive: bool

    @property
    def end(self) -> date:
        """The day after the chosen period ends."""
        return period_end(self.start, self.period)


@dataclass(frozen=True, slots=True)
class Layout:
    """Which cards and categories are pinned to the top or hidden.

    Entries are card keys (``activity.steps``) or category names (``sleep``),
    which cover every card of that category.

    Attributes:
        pinned: Pinned entries, in the order they were pinned.
        hidden: Hidden entries.
    """

    pinned: tuple[str, ...] = ()
    hidden: tuple[str, ...] = ()

    def is_hidden(self, key: str) -> bool:
        """Tell whether a card or category is hidden.

        Args:
            key: A card key or a category name.

        Returns:
            True if it, or its category, is hidden.
        """
        return key in self.hidden or key.split(".")[0] in self.hidden

    def pin_rank(self, key: str) -> int | None:
        """Return where a card or category sits among the pins.

        Args:
            key: A card key or a category name.

        Returns:
            Its position among the pinned entries (its own or its category's,
            whichever comes first), or None when it isn't pinned.
        """
        ranks = [
            rank
            for rank, entry in enumerate(self.pinned)
            if entry in (key, key.split(".")[0])
        ]
        return min(ranks, default=None)


@dataclass(frozen=True, slots=True)
class Reading:
    """The numbers behind a card, in display units.

    Attributes:
        unit: The display unit.
        daily: Values by date.
        values: Values by period start.
        current: The selected period's value.
        previous: The period before's value, or None.
        usual: The usual range, or None without enough history.
        assessment: The comparison with the usual range, when one is fair.
        comparable: False for a total of a period still in progress.
        stale_since: When the value last changed, if it is now stale.
        latest_day: For a "latest" metric with no reading in the period, the date
            of the reading shown instead; otherwise None.
    """

    unit: str
    daily: Daily
    values: Daily
    current: float
    previous: float | None
    usual: UsualRange | None
    assessment: Assessment | None
    comparable: bool
    stale_since: date | None
    latest_day: date | None


class ChartKind(StrEnum):
    """The small chart a card draws, chosen by the kind of metric."""

    LINE = "line"
    BARS = "bars"
    DOTS = "dots"
    STACK = "stack"
    GRID = "grid"
    CYCLE = "cycle"
    BUDGET = "budget"


@dataclass(frozen=True, slots=True)
class CardChart:
    """What a card's small chart shows.

    Attributes:
        kind: How to draw it.
        points: (date, value) pairs: period starts for lines and bars, days for
            dots. The last one is the selected period or day.
        usual: The usual range as (low, high), drawn as a band, or None.
        goals: (date, target) pairs for a goal line; empty without a goal.
        parts: (item, date, value) triples for stacks, grids and budgets.
        targets: (item, target) pairs, e.g. each category's budget for the period.
        window: The first and last day a cycle strip covers.
        unit: The display unit, for tooltips.
    """

    kind: ChartKind
    points: tuple[tuple[date, float], ...] = ()
    usual: tuple[float, float] | None = None
    goals: tuple[tuple[date, float], ...] = ()
    parts: tuple[tuple[str, date, float], ...] = ()
    targets: tuple[tuple[str, float], ...] = ()
    window: tuple[date, date] | None = None
    unit: str = ""


@dataclass(frozen=True, slots=True)
class Card:
    """Everything an Overview card shows.

    Attributes:
        key: ``category.column``, or ``category.<kind>`` for derived cards.
        area: The Overview section it belongs to.
        label: The card's title.
        value: The period's value, formatted.
        unit: What the number is, e.g. "a day".
        delta: The change since the previous period, formatted, or None.
        chip: Its status: "Usual", "Below usual", "Stale", "So far" and so on.
        color: The colour of the change and sparkline: blue, orange or gray.
        usual: The usual range in words, or empty.
        note: Extra context, e.g. a breakdown or a stale warning; may be empty.
        goal: Progress towards the metric's goal, or empty without one.
        chart: The card's small chart, or None when one would say nothing (a
            latest reading that hasn't changed).
        sensitive: Whether it is hidden until "Show sensitive" is on.
        assessment: How the value compares with the usual range, if it can.
    """

    key: str
    area: str
    label: str
    value: str
    unit: str
    delta: str | None
    chip: str
    color: Color
    usual: str
    note: str
    goal: str
    chart: CardChart | None
    sensitive: bool
    assessment: Assessment | None


@dataclass(frozen=True, slots=True)
class Overview:
    """The Overview page's content for one period.

    Attributes:
        cards: Cards with data in the period, in area order.
        notable: The cards furthest outside their usual range, good or bad.
        missing: Categories with no data in the period, with their last date.
        hidden: How many sensitive categories are hidden.
    """

    cards: tuple[Card, ...]
    notable: tuple[Card, ...]
    missing: tuple[str, ...]
    hidden: int


def category_named(dataset: Dataset, name: str) -> Category:
    """Find a loaded category by name.

    Args:
        dataset: The loaded data.
        name: The category's name.

    Returns:
        The category.

    Raises:
        KeyError: If the dataset has no such category.
    """
    for category in dataset.categories:
        if category.name == name:
            return category
    raise KeyError(f"no data for category {name!r}")


def card_specs(category: Category) -> list[CardSpec]:
    """Choose a category's Overview cards.

    Args:
        category: The category.

    Returns:
        Its cards' specs; none for life events, which only label charts.
    """
    if category.name == "events":
        return []
    if category.name == "workouts":
        return [CardSpec("workouts", None, "Workouts", Aggregate.SUM, "sessions", True)]
    if category.name == "reflections":
        return [CardSpec("reflections", None, "Reflections", Aggregate.SUM, "entries")]
    if category.name == "finances":
        return [CardSpec("finances", "amount", "Spending", Aggregate.SUM, "")]
    metrics = {metric.column: metric for metric in category.metrics}
    columns = OVERVIEW_COLUMNS.get(category.name, (category.metrics[0].column,))
    specs = [
        CardSpec(
            category.name,
            column,
            LABELS.get(f"{category.name}.{column}", metrics[column].label),
            AGGREGATE_OVERRIDES.get(
                f"{category.name}.{column}", metrics[column].aggregate
            ),
            metrics[column].unit,
            metrics[column].higher_is_better,
        )
        for column in columns
    ]
    if category.name == "sleep":
        specs.append(
            CardSpec("sleep", None, "Bedtime", Aggregate.MEAN, CLOCK, False, "start")
        )
    return specs


def spec_key(spec: CardSpec) -> str:
    """Return the key that names a card in pins, hides and widget keys.

    Args:
        spec: The card.

    Returns:
        ``category.column``, or ``category.start`` for bedtime and
        ``category.count`` for counts.
    """
    return f"{spec.category}.{spec.column or spec.clock_of or 'count'}"


def card_labels(dataset: Dataset) -> dict[str, str]:
    """Name every possible Overview card, hidden ones included.

    Args:
        dataset: The loaded data.

    Returns:
        Card labels by card key.
    """
    return {
        spec_key(spec): spec.label
        for category in dataset.categories
        for spec in card_specs(category)
    }


def trend_specs(category: Category) -> list[CardSpec]:
    """Choose a category's Trends charts: every metric, plus derived ones.

    Args:
        category: The category.

    Returns:
        One spec per chart, the Overview's derived cards (counts, clock times)
        included.
    """
    derived = [spec for spec in card_specs(category) if spec.column is None]
    metrics = [
        CardSpec(
            category.name,
            metric.column,
            LABELS.get(f"{category.name}.{metric.column}", metric.label),
            AGGREGATE_OVERRIDES.get(
                f"{category.name}.{metric.column}", metric.aggregate
            ),
            metric.unit,
            metric.higher_is_better,
        )
        for metric in category.metrics
    ]
    return derived + metrics if category.name == "workouts" else metrics + derived


def is_spending(row: Row, home: str | None) -> bool:
    """Tell whether a transaction is money spent, in the home currency if set.

    Args:
        row: A parsed transaction.
        home: The home currency code, or None to count every currency.

    Returns:
        True for outgoing money in that currency.
    """
    return cast(float, row["amount"]) < 0 and home in (None, row["currency"])


def spec_daily(spec: CardSpec, dataset: Dataset) -> Daily:
    """Work out a card's daily values from the dataset.

    Args:
        spec: The card.
        dataset: The loaded data.

    Returns:
        Values by date, in stored units. Spending is positive.
    """
    if spec.category == "reflections":
        counts = Counter(reflection.day for reflection in dataset.reflections)
        return {day: float(count) for day, count in counts.items()}
    rows = dataset.rows[spec.category]
    context = dataset.contexts[spec.category]
    if spec.clock_of is not None:
        return clock_by_day(rows, spec.clock_of, context.timezone)
    if spec.column is None:
        return daily_counts(rows)
    category = category_named(dataset, spec.category)
    if spec.category != "finances":
        return daily_values(category, rows, spec.column, context)
    home = context.options.get("home_currency")
    spent = daily_values(
        category, rows, "amount", context, lambda row: is_spending(row, home)
    )
    return {day: -value for day, value in spent.items()}


def usual_periods(config: dict[str, Any], period: Period) -> int:
    """Return how many earlier periods make up the usual range.

    Args:
        config: The whole of config.toml.
        period: Weeks or months.

    Returns:
        ``[dashboard] usual_range`` for the period, else 8 weeks or 6 months.
    """
    setting = config.get("dashboard", {}).get("usual_range", {})
    return setting.get(period.value, DEFAULT_USUAL_PERIODS[period])


def read(spec: CardSpec, dataset: Dataset, selection: Selection) -> Reading | None:
    """Work out the numbers behind a card for the selected period.

    Args:
        spec: The card.
        dataset: The loaded data.
        selection: The chosen period.

    Returns:
        The reading, or None when the period has no value.
    """
    config = dataset.source.config
    display = config.get("display", {})
    _, unit = display_value(0.0, spec.unit, display)
    daily = {
        day: display_value(value, spec.unit, display)[0]
        for day, value in spec_daily(spec, dataset).items()
    }
    values = period_values(daily, spec.aggregate, selection.period)
    current = values.get(selection.start)
    latest_day = None
    if current is None and spec.aggregate is Aggregate.LAST:
        latest_day = max((day for day in daily if day < selection.end), default=None)
        current = None if latest_day is None else daily[latest_day]
    if current is None:
        return None
    count = usual_periods(config, selection.period)
    usual = usual_range(values, selection.start, selection.period, count)
    as_of = cast(date, dataset.as_of)
    comparable = (
        as_of >= selection.end - timedelta(days=1)
        or spec.aggregate in COMPARABLE_WHILE_PARTIAL
    )
    context = dataset.contexts.get(spec.category)
    stale_after = (context.options if context else {}).get("stale_after_days", {})
    changed = last_change(daily)
    is_stale = (
        spec.column in stale_after
        and changed is not None
        and (as_of - changed).days >= stale_after[spec.column]
    )
    assessment = (
        assess(current, usual, spec.higher_is_better)
        if usual is not None and comparable and not is_stale
        else None
    )
    previous_start = previous_starts(selection.start, selection.period, 1)[0]
    return Reading(
        unit=unit,
        daily=daily,
        values=values,
        current=current,
        previous=values.get(previous_start),
        usual=usual,
        assessment=assessment,
        comparable=comparable,
        stale_since=changed if is_stale else None,
        latest_day=latest_day,
    )


def chip_and_color(reading: Reading) -> tuple[str, Color]:
    """Pick a card's status chip and colour.

    Args:
        reading: The card's numbers.

    Returns:
        The chip text and the colour name.
    """
    if reading.stale_since is not None:
        return "Stale", "gray"
    if not reading.comparable:
        return "So far", "gray"
    if reading.assessment is None:
        return "New", "gray"
    return STATUS_CHIPS[reading.assessment.status], TONE_COLORS[reading.assessment.tone]


def item_values(
    spec: CardSpec, dataset: Dataset, selection: Selection
) -> list[tuple[str, date, float]]:
    """List a card's values by item and day in the period, for breakdowns.

    Items are a daily category's one item column (a habit, a calendar category)
    or a transaction's spending category.

    Args:
        spec: The card.
        dataset: The loaded data.
        selection: The chosen period.

    Returns:
        (item, date, value) triples; empty for cards without items. Spending is
        positive.
    """
    if spec.column is None or spec.category == "reflections":
        return []
    category = category_named(dataset, spec.category)
    if spec.category == "finances":
        home = dataset.contexts["finances"].options.get("home_currency")
        item, keep = "category", lambda row: is_spending(row, home)
    else:
        items = [name for name in category.key if name != "date"]
        if category.grain is not Grain.DAY or len(items) != 1:
            return []
        item, keep = items[0], lambda row: True
    sign = -1.0 if spec.category == "finances" else 1.0
    return [
        (
            cast(str, row[item]),
            cast(date, row["date"]),
            sign * cast(float, row[spec.column]),
        )
        for row in dataset.rows[spec.category]
        if row.get(spec.column) is not None
        and selection.start <= cast(date, row["date"]) < selection.end
        and keep(row)
    ]


def item_totals(values: list[tuple[str, date, float]]) -> list[tuple[str, float]]:
    """Total item values over the period, largest first.

    Args:
        values: (item, date, value) triples from ``item_values``.

    Returns:
        (item, total) pairs.
    """
    totals: dict[str, float] = defaultdict(float)
    for item, _, value in values:
        totals[item] += value
    return sorted(totals.items(), key=lambda pair: -pair[1])


def breakdown(spec: CardSpec, dataset: Dataset, selection: Selection) -> str:
    """Split a card's period total by item, e.g. hours per calendar category.

    Args:
        spec: The card.
        dataset: The loaded data.
        selection: The chosen period.

    Returns:
        E.g. "work 38.6 · leisure 25.1", the five largest, or empty.
    """
    currency = (
        dataset.contexts["finances"].options.get("home_currency", "")
        if spec.category == "finances"
        else ""
    )
    totals = item_totals(item_values(spec, dataset, selection))[:5]
    return " · ".join(
        f"{name} {format_value(total, spec.unit, currency)}" for name, total in totals
    )


def skipped_days(spec: CardSpec, dataset: Dataset, selection: Selection) -> int:
    """Count days in the period that the category's day filter leaves out.

    Args:
        spec: The card.
        dataset: The loaded data.
        selection: The chosen period.

    Returns:
        How many of the period's rows were left out of averages.
    """
    if spec.column is None or spec.category == "reflections":
        return 0
    category = category_named(dataset, spec.category)
    if category.day_filter is None:
        return 0
    context = dataset.contexts[spec.category]
    return sum(
        selection.start <= cast(date, row["date"]) < selection.end
        and not category.day_filter(row, context)
        for row in dataset.rows[spec.category]
    )


def card_note(
    spec: CardSpec, dataset: Dataset, selection: Selection, reading: Reading
) -> str:
    """Write a card's extra context: breakdown, watch-off days, staleness.

    Args:
        spec: The card.
        dataset: The loaded data.
        selection: The chosen period.
        reading: The card's numbers.

    Returns:
        Sentences joined by full stops, or empty.
    """
    skipped = skipped_days(spec, dataset, selection)
    changed = reading.stale_since
    latest = reading.latest_day
    notes = [
        f"No new reading; latest from {latest.day} {latest:%b}"
        if latest is not None and changed is None
        else "",
        breakdown(spec, dataset, selection),
        f"{skipped} watch-off day{'s' if skipped > 1 else ''} left out"
        if skipped
        else "",
        f"Unchanged since {changed.day} {changed:%b}; left out of comparisons"
        if changed is not None
        else "",
    ]
    return ". ".join(note for note in notes if note)


def display_goal(spec: CardSpec, dataset: Dataset) -> Goal | None:
    """Return a card's goal in display units, if its metric has one.

    Args:
        spec: The card.
        dataset: The loaded data, for the goals and display settings.

    Returns:
        The goal with its target converted, or None.
    """
    if spec.column is None or spec.category == "reflections":
        return None
    category = category_named(dataset, spec.category)
    metric = next(m for m in category.metrics if m.column == spec.column)
    goal = goal_for(metric, dataset.contexts[spec.category])
    if goal is None:
        return None
    display = dataset.source.config.get("display", {})
    return Goal(display_value(goal.target, spec.unit, display)[0], goal.at_least)


def period_target(goal: Goal, aggregate: Aggregate, start: date, end: date) -> float:
    """Return a goal's target for one period.

    Totals' goals are per week, so a month's target scales with its length;
    averages and latest values keep the target as it is.

    Args:
        goal: The goal, in display units.
        aggregate: How the metric's period value is formed.
        start: The period's first day.
        end: The day after the period.

    Returns:
        The target for that period.
    """
    if aggregate in (Aggregate.SUM, Aggregate.DAYS):
        return goal.target * (end - start).days / 7
    return goal.target


def goal_text(
    spec: CardSpec,
    reading: Reading,
    goal: Goal | None,
    selection: Selection,
    currency: str,
) -> str:
    """Describe progress towards a card's goal for the selected period.

    Args:
        spec: The card.
        reading: The card's numbers.
        goal: The goal in display units, or None.
        selection: The chosen period.
        currency: The home currency code, for money.

    Returns:
        E.g. "Goal 10,000 a day: reached on 5 of 7 days", or empty.
    """
    if goal is None:
        return ""
    unit = reading.unit

    def amount(value: float) -> str:
        text = format_value(value, unit, currency)
        return text if unit in UNITLESS else f"{text} {SCALE_UNITS.get(unit, unit)}"

    prefix = "Goal " if goal.at_least else "Goal at most "
    if spec.aggregate is Aggregate.MEAN:
        days = [
            value
            for day, value in reading.daily.items()
            if selection.start <= day < selection.end
        ]
        reached = sum(goal.met(value) for value in days)
        nights = "nights" if spec.category == "sleep" else "days"
        count = f"reached on {reached} of {len(days)} {nights}"
        return f"{prefix}{amount(goal.target)}: {count}"
    target = period_target(goal, spec.aggregate, selection.start, selection.end)
    per = "" if spec.aggregate is Aggregate.LAST else f" a {selection.period.value}"
    head = f"{prefix}{amount(target)}{per}"
    if goal.met(reading.current):
        return f"{head}: reached"
    gap = amount(abs(target - reading.current))
    return f"{head}: {gap} to go" if goal.at_least else f"{head}: over by {gap}"


def last_day_shown(dataset: Dataset, selection: Selection) -> date:
    """Return the last day the selected period shows: its end, or today's data.

    Args:
        dataset: The loaded data.
        selection: The chosen period.

    Returns:
        The earlier of the period's last day and the latest date in the data.
    """
    return min(selection.end - timedelta(days=1), cast(date, dataset.as_of))


def period_budgets(dataset: Dataset, selection: Selection) -> dict[str, float]:
    """Return each category's budget for the selected period, in home currency.

    Args:
        dataset: The loaded data.
        selection: The chosen period.

    Returns:
        Budget by spending category; empty without budgets in config.
    """
    context = dataset.contexts.get("finances")
    budgets = {} if context is None else context.options.get("budgets", {})
    return budget_shares(budgets, selection.start, selection.end)


def card_chart(
    spec: CardSpec, dataset: Dataset, selection: Selection, reading: Reading
) -> CardChart | None:
    """Choose and fill a card's small chart.

    Args:
        spec: The card.
        dataset: The loaded data.
        selection: The chosen period.
        reading: The card's numbers.

    Returns:
        The chart, or None for a latest reading that is stale or not from the period.
    """
    if reading.stale_since is not None or reading.latest_day is not None:
        return None
    if spec.category == "cycle":
        last = last_day_shown(dataset, selection)
        first = last - timedelta(days=CYCLE_WINDOW_DAYS - 1)
        days = tuple(
            sorted((d, v) for d, v in reading.daily.items() if first <= d <= last)
        )
        return CardChart(ChartKind.CYCLE, days, window=(first, last), unit=reading.unit)
    parts = item_values(spec, dataset, selection)
    budgets = period_budgets(dataset, selection) if spec.category == "finances" else {}
    if parts and budgets:
        targets = tuple(sorted(budgets.items()))
        currency = dataset.contexts["finances"].options.get("home_currency", "")
        return CardChart(
            ChartKind.BUDGET, parts=tuple(parts), targets=targets, unit=currency
        )
    if parts:
        kind = ChartKind.GRID if spec.category == "habits" else ChartKind.STACK
        return CardChart(kind, parts=tuple(parts), unit=reading.unit)
    if spec.clock_of is not None:
        nights = sorted(
            (day, value)
            for day, value in reading.daily.items()
            if selection.start <= day < selection.end
        )
        usual = reading.usual
        band = None if usual is None else (usual.low, usual.high)
        return CardChart(ChartKind.DOTS, tuple(nights), band, unit=reading.unit)
    earlier = previous_starts(selection.start, selection.period, SERIES_LENGTH - 1)
    starts = [*reversed(earlier), selection.start]
    points = tuple(
        (start, reading.values[start]) for start in starts if start in reading.values
    )
    context_only = AREA_OF.get(spec.category) == "Context"
    usual = None if reading.usual is None or context_only else reading.usual
    goal = display_goal(spec, dataset)
    goals = (
        ()
        if goal is None
        else tuple(
            (
                start,
                period_target(
                    goal, spec.aggregate, start, period_end(start, selection.period)
                ),
            )
            for start, _ in points
        )
    )
    kind = (
        ChartKind.BARS
        if spec.aggregate in (Aggregate.SUM, Aggregate.DAYS)
        else ChartKind.LINE
    )
    band = None if usual is None else (usual.low, usual.high)
    return CardChart(kind, points, band, goals, unit=reading.unit)


def build_card(spec: CardSpec, dataset: Dataset, selection: Selection) -> Card | None:
    """Build one card for the selected period.

    Args:
        spec: The card.
        dataset: The loaded data.
        selection: The chosen period and options.

    Returns:
        The card, or None when the period has no value for it.
    """
    reading = read(spec, dataset, selection)
    if reading is None:
        return None
    currency = (
        dataset.contexts["finances"].options.get("home_currency", "")
        if spec.category == "finances"
        else ""
    )
    unit = reading.unit

    def shown(value: float) -> str:
        return format_value(value, unit, currency)

    chip, color = chip_and_color(reading)
    usual = reading.usual
    card = Card(
        key=spec_key(spec),
        area=AREA_OF.get(spec.category, AREAS[-1]),
        label=spec.label,
        value=shown(reading.current),
        unit=unit_label(
            unit,
            spec.aggregate,
            selection.period,
            night=spec.category == "sleep",
        ),
        delta=None
        if reading.previous is None
        else format_delta(reading.current - reading.previous, unit, currency),
        chip=chip,
        color=color,
        usual=""
        if usual is None
        else f"Usual {shown(usual.low)} to {shown(usual.high)}",
        note=card_note(spec, dataset, selection, reading),
        goal=goal_text(spec, reading, display_goal(spec, dataset), selection, currency),
        chart=card_chart(spec, dataset, selection, reading),
        sensitive=category_named(dataset, spec.category).sensitive,
        assessment=reading.assessment,
    )
    if spec.category == "cycle":
        return with_cycle(card, dataset, selection, reading.daily)
    if spec.category == "finances":
        note = budget_note(dataset, selection, currency)
        return replace(card, note=". ".join(part for part in (card.note, note) if part))
    return card


def with_cycle(
    card: Card, dataset: Dataset, selection: Selection, daily: Daily
) -> Card:
    """Describe the cycle instead of a count: the day of the cycle and its dates.

    Args:
        card: The generic card for flow.
        dataset: The loaded data.
        selection: The chosen period.
        daily: Flow level by date.

    Returns:
        The card with the cycle day as its value and the period dates as its note.
    """
    status = cycle_status(daily, last_day_shown(dataset, selection))
    if status is None:
        return card
    note = (
        f"Last period {status.last_start.day} {status.last_start:%b} to "
        f"{status.last_end.day} {status.last_end:%b}"
    )
    expected = status.next_expected
    if expected is not None:
        note += (
            f". Typical cycle {status.typical_length} days; next expected around "
            f"{expected.day} {expected:%b}"
        )
    return replace(
        card,
        value=f"Day {status.day}",
        unit="of cycle",
        delta=None,
        chip="Cycle",
        color="gray",
        usual="",
        note=note,
        assessment=None,
    )


def budget_note(dataset: Dataset, selection: Selection, currency: str) -> str:
    """Compare spending with each budget for the selected period.

    Args:
        dataset: The loaded data.
        selection: The chosen period.
        currency: The home currency code.

    Returns:
        E.g. "Budgets: books £43.91 of £40.00 (over) · coffee £26.94 of £60.00",
        or empty without budgets.
    """
    budgets = period_budgets(dataset, selection)
    if not budgets:
        return ""
    spec = CardSpec("finances", "amount", "Spending", Aggregate.SUM, "")
    spent = dict(item_totals(item_values(spec, dataset, selection)))

    def line(category: str, budget: float) -> str:
        used = spent.get(category, 0.0)
        over = " (over)" if used > budget else ""
        money = format_value(used, "", currency)
        return f"{category} {money} of {format_value(budget, '', currency)}{over}"

    return "Budgets: " + " · ".join(line(c, b) for c, b in sorted(budgets.items()))


def with_stuck_note(
    card: Card, dataset: Dataset, selection: Selection, cards: list[Card]
) -> Card:
    """Note when a card's value stayed flat while its related metrics moved.

    Args:
        card: The card.
        dataset: The loaded data.
        selection: The chosen period; its usual-range window is where the value
            should have changed.
        cards: All cards, which hold the related metrics' assessments.

    Returns:
        The card, with a note added if it is stuck.
    """
    category_name, column = card.key.split(".")
    category = category_named(dataset, category_name)
    metric = next((m for m in category.metrics if m.column == column), None)
    by_key = {other.key: other for other in cards if other.assessment is not None}
    related = {
        key: cast(Assessment, by_key[key].assessment)
        for key in (metric.related if metric else ())
        if key in by_key
    }
    if not related:
        return card
    daily = daily_values(
        category, dataset.rows[category_name], column, dataset.contexts[category_name]
    )
    count = usual_periods(dataset.source.config, selection.period)
    since = previous_starts(selection.start, selection.period, count)[-1]
    moved = stuck_against(daily, related, since)
    if not moved:
        return card
    names = " and ".join(by_key[key].label.lower() for key in moved)
    note = f"Flat while {names} moved; the source may have stopped updating"
    return replace(card, note=". ".join(part for part in (card.note, note) if part))


def missing_note(spec: CardSpec, dataset: Dataset) -> str:
    """Describe a card with no data in the selected period.

    Args:
        spec: The card.
        dataset: The loaded data.

    Returns:
        E.g. "blood glucose (last 14 Jun)".
    """
    last = max(spec_daily(spec, dataset), default=None)
    when = "" if last is None else f" (last {last.day} {last:%b})"
    return f"{spec.label.lower()}{when}"


def build_overview(
    dataset: Dataset, selection: Selection, layout: Layout | None = None
) -> Overview:
    """Build the Overview for the selected period.

    Args:
        dataset: The loaded data.
        selection: The chosen period and options.
        layout: Pins and hides; hidden cards and categories are left out,
            including from "Notable".

    Returns:
        The cards to show, the notable ones, what has no data, and what is hidden.
    """
    shown = [
        category
        for category in dataset.categories
        if selection.show_sensitive or not category.sensitive
    ]
    layout = Layout() if layout is None else layout
    specs = [
        spec
        for category in shown
        if not layout.is_hidden(category.name)
        for spec in card_specs(category)
        if not layout.is_hidden(spec_key(spec))
    ]
    built = [(spec, build_card(spec, dataset, selection)) for spec in specs]
    cards = [card for _, card in built if card is not None]
    cards = [with_stuck_note(card, dataset, selection, cards) for card in cards]
    cards.sort(key=lambda card: AREAS.index(card.area))
    assessed = {card.key: card.assessment for card in cards if card.assessment}
    by_key = {card.key: card for card in cards}
    return Overview(
        cards=tuple(cards),
        notable=tuple(by_key[key] for key in notable(assessed, NOTABLE_LIMIT)),
        missing=tuple(
            missing_note(spec, dataset) for spec, card in built if card is None
        ),
        hidden=len(dataset.categories) - len(shown),
    )
