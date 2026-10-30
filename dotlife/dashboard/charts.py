from collections import defaultdict
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import cast

import altair as alt
import polars as pl

from dotlife.dashboard.cards import CardChart, ChartKind, Trend, TrendKind
from dotlife.dashboard.display import CLOCK, format_value
from dotlife.summaries import UNRECORDED_FLOW

EVENING_MINUTES = 18 * 60
CLOCK_LABEL = (
    "format(floor(((datum.value + 1080) % 1440) / 60), '02d') + ':' + "
    "format((datum.value + 1080) % 60, '02d')"
)
HOURS_LABEL = (
    "format(floor(datum.value / 60), 'd') + ' h ' + "
    "format(round(datum.value % 60), '02d') + ' m'"
)


def axis_for(unit: str, title: str) -> alt.Axis:
    """Build a y axis that labels clock times and durations the way cards do.

    Args:
        unit: The display unit; ``clock`` and ``min`` get custom labels.
        title: The axis title.

    Returns:
        The axis.
    """
    if unit == CLOCK:
        return alt.Axis(title=title, labelExpr=CLOCK_LABEL)
    if unit == "min":
        return alt.Axis(title=title, labelExpr=HOURS_LABEL)
    return alt.Axis(title=title)


TREND_HEIGHT = 240
BAR_INSET = 0.12
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
RATING_RAMPS = {
    True: ("#BFDBFE", "#1D4ED8"),
    False: ("#FED7AA", "#C2410C"),
    None: ("#D4D4D8", "#3F3F46"),
}
ALT_TEXT = {
    TrendKind.TOTALS: "bars of each period's total",
    TrendKind.DAYS: "each day as a dot, with each period's average as a line",
    TrendKind.CALENDAR: "a calendar with each day shaded by its rating",
    TrendKind.READINGS: "a line stepping from one reading to the next",
    TrendKind.MATRIX: "a square per item and period, shaded by days done",
    TrendKind.STACK: "stacked bars of each part, per period",
    TrendKind.RANGE: "a bar from the low to the high value, per period",
}


def period_name(start: date, end: date) -> str:
    """Name a period for tooltips.

    Args:
        start: Its first day.
        end: The day after its last.

    Returns:
        E.g. "Week of 24 Aug 2026" or "August 2026".
    """
    if (end - start).days <= 7:
        return f"Week of {start.day} {start:%b %Y}"
    return f"{start:%B %Y}"


def inset(start: date, end: date) -> tuple[datetime, datetime]:
    """Narrow a period to a bar, leaving a gap on each side.

    Args:
        start: The period's first day.
        end: The day after its last.

    Returns:
        The bar's left and right edges.
    """
    gap = (end - start) * BAR_INSET
    left = datetime.combine(start, datetime.min.time())
    return left + gap, left + (end - start) - gap


def middle(start: date, end: date) -> datetime:
    """Return the middle of a period, where its average sits among its days.

    Args:
        start: The period's first day.
        end: The day after its last.

    Returns:
        The moment halfway through.
    """
    return datetime.combine(start, datetime.min.time()) + (end - start) / 2


def time_axis(trend: Trend) -> alt.X:
    """Build the shared x axis, so every chart on the page lines up.

    Args:
        trend: The chart's content.

    Returns:
        A time axis from the first day shown to the end of the selected period.
    """
    return alt.X(
        "x:T",
        title=None,
        axis=alt.Axis(
            format="%b %Y",
            labelAngle=0,
            grid=False,
            tickCount=alt.TimeIntervalStep(interval="month", step=1),
        ),
        scale=alt.Scale(domain=[trend.first.isoformat(), trend.end.isoformat()]),
    )


def context_layers(
    trend: Trend, events: Sequence[tuple[date, str]]
) -> tuple[list[alt.Chart], list[alt.Chart]]:
    """Draw the usual range and goal behind the data, and life events over it.

    Args:
        trend: The chart's content.
        events: (date, label) life events; those outside the chart are left out.

    Returns:
        Layers to draw under the data, and layers to draw over it.
    """
    under: list[alt.Chart] = []
    if trend.usual is not None:
        band = pl.DataFrame({"low": [trend.usual[0]], "high": [trend.usual[1]]})
        under.append(
            alt.Chart(band)
            .mark_rect(opacity=0.12, color="gray")
            .encode(y="low:Q", y2="high:Q")
        )
    if trend.goals:
        goals = pl.DataFrame(
            {
                "x": [start for start, _, _ in trend.goals],
                "x2": [end for _, end, _ in trend.goals],
                "goal": [target for *_, target in trend.goals],
                "label": [
                    format_value(target, trend.unit, trend.currency)
                    for *_, target in trend.goals
                ],
            }
        )
        under.append(
            alt.Chart(goals)
            .mark_rule(strokeDash=[6, 4], strokeWidth=1.5, color=GOAL_HEX)
            .encode(
                x=time_axis(trend),
                x2="x2:T",
                y="goal:Q",
                tooltip=[alt.Tooltip("label:N", title="Goal")],
            )
        )
    shown = [(day, label) for day, label in events if trend.first <= day < trend.end]
    if not shown:
        return under, []
    marks = pl.DataFrame(
        {"x": [day for day, _ in shown], "label": [label for _, label in shown]}
    )
    tooltip = [
        alt.Tooltip("label:N", title="Life event"),
        alt.Tooltip("x:T", title="Date", format="%-d %b %Y"),
    ]
    rule = (
        alt.Chart(marks)
        .mark_rule(strokeDash=[3, 3], color="gray")
        .encode(x=time_axis(trend), tooltip=tooltip)
    )
    hover_area = (
        alt.Chart(marks)
        .mark_rule(strokeWidth=12, opacity=0)
        .encode(x=time_axis(trend), tooltip=tooltip)
    )
    return under, [rule, hover_area]


def value_axis(trend: Trend, field: str = "value", zero: bool = False) -> alt.Y:
    """Build the y axis for a chart's values.

    Args:
        trend: The chart's content.
        field: The column holding the values.
        zero: Whether the axis starts at zero, as bars must.

    Returns:
        The axis, labelled like the cards.
    """
    return alt.Y(
        f"{field}:Q",
        title=None,
        axis=axis_for(trend.unit, ""),
        scale=alt.Scale(zero=zero),
    )


def total_bars(trend: Trend) -> alt.Chart:
    """Draw each period's total as a bar, split by item when there are items.

    Args:
        trend: The chart's content.

    Returns:
        The bars; the selected period is fainter while it is still in progress.
    """
    rows = trend.parts or tuple(("", *period) for period in trend.periods)
    edges = [inset(start, end) for _, start, end, _ in rows]
    last = trend.periods[-1][0] if trend.periods else None
    stacked: dict[date, float] = defaultdict(float)
    bottoms, tops = [], []
    for _, start, _, value in rows:
        bottoms.append(stacked[start])
        stacked[start] += value
        tops.append(stacked[start])
    frame = pl.DataFrame(
        {
            "x": [left for left, _ in edges],
            "x2": [right for _, right in edges],
            "item": [item for item, *_ in rows],
            "bottom": bottoms,
            "top": tops,
            "period": [period_name(start, end) for _, start, end, _ in rows],
            "label": [
                format_value(value, trend.unit, trend.currency) for *_, value in rows
            ],
            "partial": [trend.partial and start == last for _, start, _, _ in rows],
        }
    )
    tooltip = [
        alt.Tooltip("period:N", title="Period"),
        alt.Tooltip("label:N", title="Total"),
    ]
    items = list(dict.fromkeys(item for item, *_ in rows))
    color = (
        alt.Color("item:N", sort=items, legend=alt.Legend(orient="top", title=None))
        if trend.parts
        else alt.value(STATUS_HEX["blue"])
    )
    if trend.parts:
        tooltip.insert(1, alt.Tooltip("item:N", title="Item"))
    return (
        alt.Chart(frame)
        .mark_bar(cornerRadius=2)
        .encode(
            x=time_axis(trend),
            x2="x2:T",
            y=value_axis(trend, "bottom", zero=True),
            y2="top:Q",
            color=color,
            opacity=alt.condition("datum.partial", alt.value(0.45), alt.value(1.0)),
            tooltip=tooltip,
        )
    )


def day_dots(trend: Trend) -> list[alt.Chart]:
    """Draw each day as a faint dot and each period's average as a line over them.

    Args:
        trend: The chart's content.

    Returns:
        The dots and the line.
    """
    days = pl.DataFrame(
        {
            "x": [day for day, _ in trend.days],
            "value": [value for _, value in trend.days],
            "day": [f"{day:%a} {day.day} {day:%b %Y}" for day, _ in trend.days],
            "label": [format_value(value, trend.unit) for _, value in trend.days],
        }
    )
    periods = pl.DataFrame(
        {
            "x": [middle(start, end) for start, end, _ in trend.periods],
            "value": [value for *_, value in trend.periods],
            "period": [period_name(start, end) for start, end, _ in trend.periods],
            "label": [format_value(value, trend.unit) for *_, value in trend.periods],
        }
    )
    y = value_axis(trend)
    dots = (
        alt.Chart(days)
        .mark_circle(size=16, opacity=0.5, color=MUTED_HEX)
        .encode(
            x=time_axis(trend),
            y=y,
            tooltip=[
                alt.Tooltip("day:N", title="Day"),
                alt.Tooltip("label:N", title="Value"),
            ],
        )
    )
    line = (
        alt.Chart(periods)
        .mark_line(point=alt.OverlayMarkDef(filled=True, size=36), strokeWidth=2)
        .encode(
            x=time_axis(trend),
            y=y,
            color=alt.value(STATUS_HEX["blue"]),
            tooltip=[
                alt.Tooltip("period:N", title="Period"),
                alt.Tooltip("label:N", title="Average"),
            ],
        )
    )
    return [dots, line]


def rating_calendar(trend: Trend) -> list[alt.Chart]:
    """Draw a square per day in weekday rows, shaded by the day's rating.

    Args:
        trend: The chart's content; its unit is the scale, e.g. ``1-5``.

    Returns:
        The calendar's layers; days without a rating stay as faint empty squares.
    """
    low, high = (float(end) for end in trend.unit.split("-"))
    rated = dict(trend.days)
    last = trend.days[-1][0] if trend.days else trend.first
    count = (min(trend.end, last + timedelta(days=1)) - trend.first).days
    days = [trend.first + timedelta(days=offset) for offset in range(count)]
    weeks = [day - timedelta(days=day.weekday()) for day in days]
    frame = pl.DataFrame(
        {
            "x": weeks,
            "x2": [week + timedelta(days=6) for week in weeks],
            "weekday": [WEEKDAYS[day.weekday()] for day in days],
            "day": [f"{day:%a} {day.day} {day:%b %Y}" for day in days],
            "value": [rated.get(day) for day in days],
            "label": [
                "not recorded"
                if day not in rated
                else format_value(rated[day], trend.unit)
                for day in days
            ],
        },
        schema_overrides={"value": pl.Float64},
    )
    y = alt.Y(
        "weekday:O",
        sort=list(WEEKDAYS),
        title=None,
        axis=alt.Axis(ticks=False, domain=False),
        scale=alt.Scale(paddingInner=0.2),
    )
    base = (
        alt.Chart(frame)
        .encode(
            x=time_axis(trend),
            x2="x2:T",
            y=y,
            tooltip=[
                alt.Tooltip("day:N", title="Day"),
                alt.Tooltip("label:N", title="Rating"),
            ],
        )
        .properties(height=alt.Step(18))
    )
    empty = base.mark_rect(cornerRadius=2, color="gray", opacity=0.15)
    rated = (
        base.mark_rect(cornerRadius=2)
        .transform_filter("isValid(datum.value)")
        .encode(
            color=alt.Color(
                "value:Q",
                scale=alt.Scale(
                    domain=[low, high],
                    range=list(RATING_RAMPS[trend.higher_is_better]),
                ),
                legend=alt.Legend(orient="top", title=None, gradientLength=160),
            )
        )
    )
    return [empty, rated]


def reading_steps(trend: Trend) -> list[alt.Chart]:
    """Draw a line that holds each reading until the next one, to the chart's end.

    Args:
        trend: The chart's content: one value per day with a new reading.

    Returns:
        The line and a dot at each reading.
    """
    frame = pl.DataFrame(
        {
            "x": [day for day, _ in trend.days],
            "value": [value for _, value in trend.days],
            "day": [f"{day.day} {day:%b %Y}" for day, _ in trend.days],
            "label": [format_value(value, trend.unit) for _, value in trend.days],
        }
    )
    steps = [*trend.days, (trend.end, trend.days[-1][1])] if trend.days else []
    held = pl.DataFrame(
        {
            "x": [day for day, _ in steps],
            "value": [value for _, value in steps],
        },
        schema={"x": pl.Date, "value": pl.Float64},
    )
    y = value_axis(trend)
    line = (
        alt.Chart(held)
        .mark_line(interpolate="step-after", strokeWidth=2, color=STATUS_HEX["blue"])
        .encode(x=time_axis(trend), y=y)
    )
    dots = (
        alt.Chart(frame)
        .mark_circle(size=60, opacity=1, color=STATUS_HEX["blue"])
        .encode(
            x=time_axis(trend),
            y=y,
            tooltip=[
                alt.Tooltip("day:N", title="Reading on"),
                alt.Tooltip("label:N", title="Value"),
            ],
        )
    )
    return [line, dots]


def done_matrix(trend: Trend) -> alt.Chart:
    """Draw a row per item and a square per period, shaded by the share of days done.

    Args:
        trend: The chart's content: (item, start, end, days done) parts.

    Returns:
        The matrix.
    """
    edges = [inset(start, end) for _, start, end, _ in trend.parts]
    frame = pl.DataFrame(
        {
            "x": [left for left, _ in edges],
            "x2": [right for _, right in edges],
            "item": [item for item, *_ in trend.parts],
            "share": [done / (end - start).days for _, start, end, done in trend.parts],
            "period": [period_name(start, end) for _, start, end, _ in trend.parts],
            "label": [
                f"{done:.0f} of {(end - start).days} days"
                for _, start, end, done in trend.parts
            ],
        }
    )
    return (
        alt.Chart(frame)
        .mark_rect(cornerRadius=2)
        .encode(
            x=time_axis(trend),
            x2="x2:T",
            y=alt.Y(
                "item:N",
                sort=None,
                title=None,
                axis=alt.Axis(ticks=False, domain=False, labelLimit=140),
                scale=alt.Scale(paddingInner=0.2),
            ),
            color=alt.Color(
                "share:Q",
                scale=alt.Scale(domain=[0, 1], range=list(RATING_RAMPS[True])),
                legend=alt.Legend(
                    orient="top", title=None, format="%", gradientLength=160
                ),
            ),
            tooltip=[
                alt.Tooltip("item:N", title="Item"),
                alt.Tooltip("period:N", title="Period"),
                alt.Tooltip("label:N", title="Done"),
            ],
        )
        .properties(height=alt.Step(20))
    )


def range_bars(trend: Trend) -> alt.Chart:
    """Draw a bar from each period's low value to its high one, e.g. blood pressure.

    Args:
        trend: The chart's content: the low part's values, then the high part's.

    Returns:
        The bars.
    """
    low_name = trend.parts[0][0]
    lows = {start: value for name, start, _, value in trend.parts if name == low_name}
    pairs = [
        (start, end, lows[start], value)
        for name, start, end, value in trend.parts
        if name != low_name and start in lows
    ]
    frame = pl.DataFrame(
        {
            "x": [middle(start, end) for start, end, _, _ in pairs],
            "low": [low for *_, low, _ in pairs],
            "high": [high for *_, high in pairs],
            "period": [period_name(start, end) for start, end, _, _ in pairs],
            "label": [
                f"{format_value(high, trend.unit)}/{format_value(low, trend.unit)} "
                f"{trend.unit}"
                for *_, low, high in pairs
            ],
        }
    )
    tooltip = [
        alt.Tooltip("period:N", title="Period"),
        alt.Tooltip("label:N", title="Average"),
    ]
    return (
        alt.Chart(frame)
        .mark_rule(strokeWidth=6, strokeCap="round", color=STATUS_HEX["blue"])
        .encode(
            x=time_axis(trend),
            y=alt.Y("low:Q", title=None, scale=alt.Scale(zero=False)),
            y2="high:Q",
            tooltip=tooltip,
        )
    )


def trend_chart(trend: Trend, events: Sequence[tuple[date, str]]) -> alt.LayerChart:
    """Draw a Trends chart in the form that suits its numbers.

    Args:
        trend: The chart's content.
        events: (date, label) life events, drawn as dashed lines.

    Returns:
        A layered Altair chart on a time axis shared by the whole page.
    """
    under, over = context_layers(trend, events)
    if trend.kind in (TrendKind.TOTALS, TrendKind.STACK):
        marks = [total_bars(trend)]
    elif trend.kind is TrendKind.DAYS:
        marks = day_dots(trend)
    elif trend.kind is TrendKind.CALENDAR:
        marks = rating_calendar(trend)
    elif trend.kind is TrendKind.READINGS:
        marks = reading_steps(trend)
    elif trend.kind is TrendKind.MATRIX:
        marks = [done_matrix(trend)]
    else:
        marks = [range_bars(trend)]
    sized = trend.kind not in (TrendKind.CALENDAR, TrendKind.MATRIX)
    chart = alt.LayerChart(layer=[*under, *marks, *over])
    return chart.properties(height=TREND_HEIGHT) if sized else chart


def nights_chart(nights: Sequence[tuple[str, datetime, datetime, str]]) -> alt.Chart:
    """Draw a week's nights as bars from bedtime to wake-up, 21:00 to 09:00.

    Args:
        nights: (day label, bedtime, wake time, time asleep text) per night, in
            local time.

    Returns:
        An Altair bar chart.
    """

    def evening_minutes(moment: datetime) -> int:
        return (moment.hour * 60 + moment.minute - EVENING_MINUTES) % 1440

    frame = pl.DataFrame(
        {
            "day": [day for day, *_ in nights],
            "bed": [evening_minutes(bed) for _, bed, _, _ in nights],
            "wake": [evening_minutes(wake) for _, _, wake, _ in nights],
            "in_bed": [f"{bed:%H:%M} to {wake:%H:%M}" for _, bed, wake, _ in nights],
            "asleep": [asleep for *_, asleep in nights],
        }
    )
    scale = alt.Scale(domain=[180, 900])
    return (
        alt.Chart(frame)
        .mark_bar(cornerRadius=4, height=16)
        .encode(
            y=alt.Y("day:N", sort=None, title=None),
            x=alt.X(
                "bed:Q",
                scale=scale,
                title=None,
                axis=alt.Axis(labelExpr=CLOCK_LABEL, values=[180, 360, 540, 720, 900]),
            ),
            x2="wake:Q",
            tooltip=[
                alt.Tooltip("day:N", title="Night"),
                alt.Tooltip("in_bed:N", title="In bed"),
                alt.Tooltip("asleep:N", title="Asleep"),
            ],
        )
        .properties(height=alt.Step(26))
    )


MINI_HEIGHT = 64
STATUS_HEX = {
    "green": "#16A34A",
    "blue": "#3B82F6",
    "orange": "#F97316",
    "gray": "#71717A",
}
MUTED_HEX = "#A1A1AA"
GOAL_HEX = "#16A34A"


def mini_base(frame: pl.DataFrame) -> alt.Chart:
    """Start a card chart: no axes, no grid, card height.

    Args:
        frame: The chart's data.

    Returns:
        A bare chart to add marks to.
    """
    return alt.Chart(frame).properties(height=MINI_HEIGHT)


def mini_band(usual: tuple[float, float] | None) -> list[alt.Chart]:
    """Draw the usual range as a soft band, if there is one.

    Args:
        usual: (low, high), or None.

    Returns:
        Zero or one layer.
    """
    if usual is None:
        return []
    band = pl.DataFrame({"low": [usual[0]], "high": [usual[1]]})
    return [
        mini_base(band)
        .mark_rect(opacity=0.12, color="gray")
        .encode(y=alt.Y("low:Q", axis=None), y2="high:Q")
    ]


def mini_goal(goals: Sequence[tuple[date, float]], x: str) -> list[alt.Chart]:
    """Draw the goal as a dashed line, if there is one.

    Args:
        goals: (date, target) pairs.
        x: The x field type, e.g. ``period:T``.

    Returns:
        Zero or one layer.
    """
    if not goals:
        return []
    frame = pl.DataFrame(
        {"period": [day for day, _ in goals], "goal": [g for _, g in goals]}
    )
    return [
        mini_base(frame)
        .mark_line(strokeDash=[4, 3], strokeWidth=1.25, color=GOAL_HEX)
        .encode(x=alt.X(x, axis=None), y=alt.Y("goal:Q", axis=None))
    ]


def series_chart(chart: CardChart, color: str) -> alt.LayerChart:
    """Draw a card's recent periods as a line (averages) or bars (totals).

    Args:
        chart: The card's chart data; the last point is the selected period.
        color: The card's status colour name.

    Returns:
        The layered chart.
    """
    last = len(chart.points) - 1
    frame = pl.DataFrame(
        {
            "period": [day for day, _ in chart.points],
            "value": [value for _, value in chart.points],
            "label": [format_value(value, chart.unit) for _, value in chart.points],
            "current": [index == last for index in range(len(chart.points))],
        }
    )
    x = alt.X("period:T", axis=None)
    y = alt.Y("value:Q", axis=None, scale=alt.Scale(zero=chart.kind == ChartKind.BARS))
    tooltip = [
        alt.Tooltip("period:T", title="From", format="%-d %b %Y"),
        alt.Tooltip("label:N", title="Value"),
    ]
    paint = alt.condition(
        "datum.current", alt.value(STATUS_HEX[color]), alt.value(MUTED_HEX)
    )
    if chart.kind == ChartKind.BARS:
        marks = [
            mini_base(frame)
            .mark_bar(cornerRadius=2)
            .encode(x=x, y=y, color=paint, tooltip=tooltip)
        ]
    else:
        line = (
            mini_base(frame)
            .mark_line(strokeWidth=1.75, color=MUTED_HEX)
            .encode(x=x, y=y)
        )
        dots = (
            mini_base(frame)
            .mark_point(filled=True)
            .encode(
                x=x,
                y=y,
                color=paint,
                size=alt.condition("datum.current", alt.value(60), alt.value(14)),
                tooltip=tooltip,
            )
        )
        marks = [line, dots]
    return alt.LayerChart(
        layer=[*mini_band(chart.usual), *marks, *mini_goal(chart.goals, "period:T")]
    )


def dots_chart(chart: CardChart, color: str) -> alt.LayerChart:
    """Draw each night's bedtime in the period as a dot on a time scale.

    Args:
        chart: The card's chart data: (day, minutes after 18:00) points.
        color: The card's status colour name.

    Returns:
        The layered chart.
    """
    frame = pl.DataFrame(
        {
            "night": [f"{day:%a} {day.day}" for day, _ in chart.points],
            "minutes": [value for _, value in chart.points],
            "label": [format_value(value, CLOCK) for _, value in chart.points],
        }
    )
    dots = (
        mini_base(frame)
        .mark_point(filled=True, size=40, color=STATUS_HEX[color])
        .encode(
            x=alt.X("night:N", sort=None, axis=None),
            y=alt.Y("minutes:Q", axis=None, scale=alt.Scale(zero=False, reverse=True)),
            tooltip=[
                alt.Tooltip("night:N", title="Night"),
                alt.Tooltip("label:N", title="Bedtime"),
            ],
        )
    )
    return alt.LayerChart(layer=[*mini_band(chart.usual), dots])


def stack_chart(chart: CardChart) -> alt.Chart:
    """Draw the period's total split by item as one stacked bar.

    Args:
        chart: The card's chart data: (item, day, value) parts.

    Returns:
        The chart; its colours come from the theme's categorical palette.
    """
    totals: dict[str, float] = {}
    for item, _, value in chart.parts:
        totals[item] = totals.get(item, 0.0) + value
    ranked = sorted(totals.items(), key=lambda pair: -pair[1])
    frame = pl.DataFrame(
        {
            "item": [item for item, _ in ranked],
            "value": [value for _, value in ranked],
            "label": [format_value(value, chart.unit) for _, value in ranked],
            "order": list(range(len(ranked))),
        }
    )
    return (
        alt.Chart(frame)
        .mark_bar(height=18, cornerRadius=3)
        .encode(
            x=alt.X("value:Q", stack="normalize", axis=None),
            color=alt.Color("item:N", legend=None, sort=[item for item, _ in ranked]),
            order="order:Q",
            tooltip=[
                alt.Tooltip("item:N", title="Item"),
                alt.Tooltip("label:N", title="Total"),
            ],
        )
        .properties(height=28)
    )


def grid_chart(chart: CardChart, start: date, days: int) -> alt.Chart:
    """Draw habits by day: a filled square for each day a habit was done.

    Args:
        chart: The card's chart data: (habit, day, count) parts.
        start: The period's first day.
        days: How many days the period has.

    Returns:
        The chart.
    """
    done = {(item, day): value for item, day, value in chart.parts}
    habits = sorted({item for item, _, _ in chart.parts})
    dates = [start + timedelta(days=offset) for offset in range(days)]
    frame = pl.DataFrame(
        {
            "habit": [habit for habit in habits for _ in dates],
            "start": [float(index) for _ in habits for index in range(len(dates))],
            "end": [index + CELL for _ in habits for index in range(len(dates))],
            "day": [f"{day:%a} {day.day}" for _ in habits for day in dates],
            "done": [
                done.get((habit, day), 0.0) > 0 for habit in habits for day in dates
            ],
        }
    )
    return (
        alt.Chart(frame)
        .mark_rect(cornerRadius=2, color=STATUS_HEX["blue"])
        .encode(
            x=alt.X("start:Q", axis=None, scale=alt.Scale(domain=[0, len(dates)])),
            x2="end:Q",
            y=alt.Y(
                "habit:N",
                axis=alt.Axis(title=None, labelLimit=110, ticks=False, domain=False),
                scale=alt.Scale(paddingInner=0.25),
            ),
            opacity=alt.condition("datum.done", alt.value(1.0), alt.value(0.15)),
            tooltip=[
                alt.Tooltip("habit:N", title="Habit"),
                alt.Tooltip("day:N", title="Day"),
                alt.Tooltip("done:N", title="Done"),
            ],
        )
        .properties(height=alt.Step(14))
    )


FLOW_WORDS = {0: "none", 1: "light", 2: "medium", 3: "heavy"}
FLOW_HEX = "#DB2777"
CELL = 0.8


def flow_word(level: float | None) -> str:
    """Name a day's flow for the cycle strip's tooltip.

    Args:
        level: The flow level, ``UNRECORDED_FLOW``, or None without a row.

    Returns:
        A word or two, e.g. "light" or "amount not recorded".
    """
    if level is None:
        return "not recorded"
    if level == UNRECORDED_FLOW:
        return "amount not recorded"
    return FLOW_WORDS.get(round(level), "")


def flow_strength(level: float | None) -> float:
    """Shade a day of the cycle strip: darker for heavier flow.

    Args:
        level: The flow level, ``UNRECORDED_FLOW``, or None without a row.

    Returns:
        The square's opacity.
    """
    if level is None:
        return 0.06
    if level == UNRECORDED_FLOW:
        return 0.6
    return 0.18 if level == 0 else 0.35 + 0.65 * level / 3


def cycle_chart(chart: CardChart) -> alt.Chart:
    """Draw the last weeks of a cycle as a strip of days, shaded by flow.

    Args:
        chart: The card's chart data: (day, flow level) points and the window.

    Returns:
        The chart: one square a day, darker for heavier flow, faint without flow
        and fainter still where nothing was recorded.
    """
    first, last = cast(tuple[date, date], chart.window)
    flow = dict(chart.points)
    days = [first + timedelta(days=offset) for offset in range((last - first).days + 1)]
    levels = [flow.get(day) for day in days]
    frame = pl.DataFrame(
        {
            "row": ["cycle"] * len(days),
            "start": [float(index) for index in range(len(days))],
            "end": [index + CELL for index in range(len(days))],
            "date": [f"{day:%a} {day.day} {day:%b}" for day in days],
            "flow": [flow_word(level) for level in levels],
            "strength": [flow_strength(level) for level in levels],
        }
    )
    return (
        alt.Chart(frame)
        .mark_rect(cornerRadius=1, color=FLOW_HEX)
        .encode(
            x=alt.X("start:Q", axis=None, scale=alt.Scale(domain=[0, len(days)])),
            x2="end:Q",
            y=alt.Y("row:N", axis=None),
            opacity=alt.Opacity("strength:Q", scale=None, legend=None),
            tooltip=[
                alt.Tooltip("date:N", title="Day"),
                alt.Tooltip("flow:N", title="Flow"),
            ],
        )
        .properties(height=alt.Step(20))
    )


def budget_chart(chart: CardChart) -> alt.LayerChart:
    """Draw spending per budgeted category, with a marker at each budget.

    Args:
        chart: The card's chart data: spending parts, budget targets, and the home
            currency code as its unit.

    Returns:
        The chart: orange bars over budget, blue bars within it.
    """
    spent: dict[str, float] = {}
    for item, _, value in chart.parts:
        spent[item] = spent.get(item, 0.0) + value
    targets = dict(chart.targets)

    def money(amount: float) -> str:
        return format_value(amount, "", chart.unit)

    frame = pl.DataFrame(
        {
            "category": list(targets),
            "spent": [spent.get(category, 0.0) for category in targets],
            "budget": list(targets.values()),
            "over": [
                spent.get(category, 0.0) > budget
                for category, budget in targets.items()
            ],
            "label": [
                f"{money(spent.get(category, 0.0))} of {money(budget)}"
                for category, budget in targets.items()
            ],
        }
    )
    y = alt.Y(
        "category:N",
        axis=alt.Axis(title=None, ticks=False, domain=False, labelLimit=100),
    )
    tooltip = [
        alt.Tooltip("category:N", title="Category"),
        alt.Tooltip("label:N", title="Spent"),
    ]
    bars = (
        alt.Chart(frame)
        .mark_bar(cornerRadius=2, height=10)
        .encode(
            x=alt.X("spent:Q", axis=None),
            y=y,
            color=alt.condition(
                "datum.over",
                alt.value(STATUS_HEX["orange"]),
                alt.value(STATUS_HEX["blue"]),
            ),
            tooltip=tooltip,
        )
    )
    marks = (
        alt.Chart(frame)
        .mark_tick(thickness=2, size=16, color=STATUS_HEX["gray"])
        .encode(x="budget:Q", y=y, tooltip=tooltip)
    )
    return alt.LayerChart(layer=[bars, marks]).properties(height=alt.Step(20))


def card_chart(
    chart: CardChart, color: str, start: date, days: int
) -> alt.Chart | alt.LayerChart:
    """Draw a card's small chart.

    Args:
        chart: The card's chart data.
        color: The card's status colour name.
        start: The selected period's first day, for habit grids.
        days: The selected period's length in days, for habit grids.

    Returns:
        The chart to show.
    """
    if chart.kind == ChartKind.DOTS:
        drawn = dots_chart(chart, color)
    elif chart.kind == ChartKind.STACK:
        drawn = stack_chart(chart)
    elif chart.kind == ChartKind.GRID:
        drawn = grid_chart(chart, start, days)
    elif chart.kind == ChartKind.CYCLE:
        drawn = cycle_chart(chart)
    elif chart.kind == ChartKind.BUDGET:
        drawn = budget_chart(chart)
    else:
        drawn = series_chart(chart, color)
    return drawn.configure_view(strokeWidth=0)
