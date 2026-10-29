from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, cast

from dotlife.dashboard.display import (
    AREA_OF,
    AREAS,
    CLOCK,
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
    clock_by_day,
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
    "cycle.flow_level": "Period days",
    "time.hours": "Time tracked",
    "medication.doses": "Medication doses",
    "symptoms.severity": "Symptom severity",
    "travel.travel_day": "Travel days",
}
AGGREGATE_OVERRIDES = {"habits.times": Aggregate.SUM}
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
        series: Recent period values for the sparkline, oldest first.
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
    series: tuple[float, ...]
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
    if category.name == "journal":
        return [CardSpec("journal", None, "Journal entries", Aggregate.SUM, "entries")]
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
    if spec.category == "journal":
        return {entry.day: 1.0 for entry in dataset.journal}
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


def breakdown(spec: CardSpec, dataset: Dataset, selection: Selection) -> str:
    """Split a card's period total by item, e.g. hours per calendar category.

    Args:
        spec: The card; only daily categories with one item column get a breakdown.
        dataset: The loaded data.
        selection: The chosen period.

    Returns:
        E.g. "work 38.6 · leisure 25.1", largest first, or empty.
    """
    if spec.column is None or spec.category == "journal":
        return ""
    category = category_named(dataset, spec.category)
    items = [name for name in category.key if name != "date"]
    if category.grain is not Grain.DAY or len(items) != 1:
        return ""
    totals: dict[str, float] = defaultdict(float)
    for row in dataset.rows[spec.category]:
        value = row.get(spec.column)
        if (
            value is not None
            and selection.start <= cast(date, row["date"]) < selection.end
        ):
            totals[cast(str, row[items[0]])] += cast(float, value)
    ranked = sorted(totals.items(), key=lambda pair: -pair[1])[:5]
    return " · ".join(
        f"{name} {format_value(total, spec.unit)}" for name, total in ranked
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
    if spec.column is None or spec.category == "journal":
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
    earlier = previous_starts(selection.start, selection.period, SERIES_LENGTH - 1)
    series = [reading.values.get(start) for start in reversed(earlier)] + [
        reading.current
    ]
    usual = reading.usual
    return Card(
        key=f"{spec.category}.{spec.column or spec.clock_of or 'count'}",
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
        series=tuple(value for value in series if value is not None),
        sensitive=category_named(dataset, spec.category).sensitive,
        assessment=reading.assessment,
    )


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


def build_overview(dataset: Dataset, selection: Selection) -> Overview:
    """Build the Overview for the selected period.

    Args:
        dataset: The loaded data.
        selection: The chosen period and options.

    Returns:
        The cards to show, the notable ones, what has no data, and what is hidden.
    """
    shown = [
        category
        for category in dataset.categories
        if selection.show_sensitive or not category.sensitive
    ]
    specs = [spec for category in shown for spec in card_specs(category)]
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
