from dataclasses import dataclass
from typing import Literal

from dotlife.periods import Period, clock_from_minutes
from dotlife.schema import Aggregate
from dotlife.summaries import Tone

AREAS = (
    "Body and health",
    "Mind",
    "Time and work",
    "Habits and leisure",
    "Money",
    "Context",
    "Your metrics",
)
AREA_OF = {
    **dict.fromkeys(
        (
            "activity",
            "workouts",
            "sleep",
            "heart",
            "body",
            "fitness_markers",
            "vitals",
            "nutrition",
            "mindfulness",
            "cycle",
            "medication",
            "symptoms",
            "glucose",
        ),
        "Body and health",
    ),
    **dict.fromkeys(("mood", "reflections"), "Mind"),
    **dict.fromkeys(("time", "screen_time", "tasks"), "Time and work"),
    **dict.fromkeys(("habits", "reading", "learning", "media"), "Habits and leisure"),
    "finances": "Money",
    **dict.fromkeys(("events", "weather", "social", "travel"), "Context"),
}
Color = Literal["blue", "orange", "gray"]
TONE_COLORS: dict[Tone, Color] = {
    Tone.GOOD: "blue",
    Tone.BAD: "orange",
    Tone.NEUTRAL: "gray",
}
CURRENCY_SYMBOLS = {"GBP": "£", "EUR": "€", "USD": "$"}
CLOCK = "clock"
SCALE_UNITS = {"1-5": "out of 5", "0-10": "out of 10", "0-3": "out of 3"}


@dataclass(frozen=True, slots=True)
class CardSpec:
    """Which number a card shows and how to get it.

    Attributes:
        category: The category name.
        column: The metric column, or None for a count of rows (e.g. workouts).
        label: The card's title.
        aggregate: How a period's daily values combine.
        unit: The unit used for formatting, or ``clock`` for times of day.
        higher_is_better: The good direction, or None when neither is.
        clock_of: For clock cards, the session timestamp to read (``start``).
    """

    category: str
    column: str | None
    label: str
    aggregate: Aggregate
    unit: str
    higher_is_better: bool | None = None
    clock_of: str | None = None


def hours_minutes(minutes: float) -> str:
    """Format a duration in minutes for people.

    Args:
        minutes: A duration in minutes, not negative.

    Returns:
        E.g. ``6 h 46 m``, or ``45 min`` under an hour.

    Example:
        >>> hours_minutes(405.6), hours_minutes(30)
        ('6 h 46 m', '30 min')
    """
    total = round(minutes)
    if total < 60:
        return f"{total} min"
    return f"{total // 60} h {total % 60:02d} m"


def number(value: float) -> str:
    """Format a plain number: whole numbers with separators, others to one decimal.

    Args:
        value: The number.

    Returns:
        E.g. ``9,661``, ``3`` or ``3.6``.

    Example:
        >>> number(9661.4), number(3.0), number(3.64)
        ('9,661', '3', '3.6')
    """
    if value.is_integer() or abs(value) >= 100:
        return f"{round(value):,}"
    return f"{value:.1f}"


def format_value(value: float, unit: str, currency: str = "") -> str:
    """Format a value for a card, by its unit.

    Args:
        value: The value, already in display units.
        unit: Its unit; ``clock`` means minutes after 18:00.
        currency: The home currency code, for money (unit ``""``).

    Returns:
        The text to show.

    Example:
        >>> format_value(342.9, "clock"), format_value(165.8, "", "GBP")
        ('23:43', '£165.80')
    """
    if unit == CLOCK:
        return f"{clock_from_minutes(value):%H:%M}"
    if unit == "min":
        return hours_minutes(value)
    if unit == "" and currency:
        return f"{CURRENCY_SYMBOLS.get(currency, currency + ' ')}{value:,.2f}"
    if unit in ("h", "kg", "lb", "°C", "mmol/L"):
        return f"{value:.1f}"
    return number(value)


def format_delta(change: float, unit: str, currency: str = "") -> str:
    """Format a change since the previous period, with its sign.

    Args:
        change: The difference, in display units.
        unit: The value's unit; clock and minute changes read as durations.
        currency: The home currency code, for money.

    Returns:
        E.g. ``-251``, ``+35 min`` or ``+0.2``; ``0`` when it rounds to nothing,
        so Streamlit shows it grey and without an arrow.

    Example:
        >>> format_delta(-250.6, "steps"), format_delta(34.9, "clock")
        ('-251', '+35 min')
        >>> format_delta(0.4, "min")
        '0'
    """
    duration = unit in (CLOCK, "min")
    size = (
        hours_minutes(abs(change))
        if duration
        else format_value(abs(change), unit, currency)
    )
    zero = hours_minutes(0) if duration else format_value(0.0, unit, currency)
    if size == zero:
        return "0"
    return ("-" if change < 0 else "+") + size


def unit_label(
    unit: str, aggregate: Aggregate, period: Period, night: bool = False
) -> str:
    """Describe what a card's number is, e.g. "a day" or "h this week".

    Args:
        unit: The display unit.
        aggregate: How the period's values combine.
        period: Weeks or months.
        night: Whether the daily value is a night's sleep.

    Returns:
        A short phrase shown next to the number.
    """
    span = f"this {period.value}"
    unit_text = SCALE_UNITS.get(unit, "" if unit in ("min", CLOCK, "steps") else unit)
    if aggregate is Aggregate.MEAN:
        each = "a night" if night else "a day"
        return each if unit_text == "" else f"{unit_text}, {each}"
    if aggregate is Aggregate.LAST:
        return f"{unit_text}, latest".strip(", ")
    if aggregate is Aggregate.DAYS:
        return f"days {span}"
    return span if unit_text == "" else f"{unit_text} {span}"
