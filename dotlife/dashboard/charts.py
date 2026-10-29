from collections.abc import Sequence
from datetime import date, datetime, timedelta

import altair as alt
import polars as pl

from dotlife.dashboard.cards import CardChart, ChartKind
from dotlife.dashboard.display import CLOCK, format_value
from dotlife.summaries import UsualRange

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


def trend_chart(
    points: Sequence[tuple[date, float]],
    unit: str,
    usual: UsualRange | None,
    events: Sequence[tuple[date, str]],
    goals: Sequence[tuple[date, float]] = (),
) -> alt.LayerChart:
    """Draw a metric's period values with its usual range and life events.

    Args:
        points: (period start, value) pairs, oldest first.
        unit: The display unit, for axis labels.
        usual: The usual range for the latest period, drawn as a band, or None.
        events: (date, label) life events inside the chart's range.
        goals: (period start, target) pairs drawn as a dashed goal line, if any.

    Returns:
        A layered Altair chart.
    """
    frame = pl.DataFrame(
        {"period": [day for day, _ in points], "value": [value for _, value in points]}
    )
    x = alt.X("period:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=0))
    y = alt.Y(
        "value:Q", title=None, axis=axis_for(unit, ""), scale=alt.Scale(zero=False)
    )
    line = (
        alt.Chart(frame)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=x,
            y=y,
            tooltip=[
                alt.Tooltip("period:T", title="Period"),
                alt.Tooltip("value:Q", title="Value", format=",.1f"),
            ],
        )
    )
    layers: list[alt.Chart] = []
    if usual is not None:
        band = pl.DataFrame({"low": [usual.low], "high": [usual.high]})
        layers.append(
            alt.Chart(band)
            .mark_rect(opacity=0.12, color="gray")
            .encode(y="low:Q", y2="high:Q")
        )
    if events:
        marks = pl.DataFrame(
            {"day": [day for day, _ in events], "label": [label for _, label in events]}
        )
        tooltip = [
            alt.Tooltip("label:N", title="Life event"),
            alt.Tooltip("day:T", title="Date", format="%-d %b %Y"),
        ]
        rule = (
            alt.Chart(marks)
            .mark_rule(strokeDash=[3, 3], color="gray")
            .encode(x="day:T", tooltip=tooltip)
        )
        hover_area = (
            alt.Chart(marks)
            .mark_rule(strokeWidth=12, opacity=0)
            .encode(x="day:T", tooltip=tooltip)
        )
        layers += [rule, hover_area]
    if goals:
        targets = pl.DataFrame(
            {
                "period": [day for day, _ in goals],
                "goal": [target for _, target in goals],
            }
        )
        layers.append(
            alt.Chart(targets)
            .mark_line(strokeDash=[6, 4], strokeWidth=1.5, color="#16A34A")
            .encode(
                x="period:T",
                y="goal:Q",
                tooltip=[alt.Tooltip("goal:Q", title="Goal", format=",.1f")],
            )
        )
    return alt.LayerChart(layer=[*layers, line]).properties(height=260)


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
STATUS_HEX = {"blue": "#3B82F6", "orange": "#F97316", "gray": "#71717A"}
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
    y = alt.Y("value:Q", axis=None, scale=alt.Scale(zero=chart.kind is ChartKind.BARS))
    tooltip = [
        alt.Tooltip("period:T", title="From", format="%-d %b %Y"),
        alt.Tooltip("label:N", title="Value"),
    ]
    paint = alt.condition(
        "datum.current", alt.value(STATUS_HEX[color]), alt.value(MUTED_HEX)
    )
    if chart.kind is ChartKind.BARS:
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
            x=alt.X("day:N", sort=None, axis=None, scale=alt.Scale(paddingInner=0.25)),
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
    if chart.kind is ChartKind.DOTS:
        drawn = dots_chart(chart, color)
    elif chart.kind is ChartKind.STACK:
        drawn = stack_chart(chart)
    elif chart.kind is ChartKind.GRID:
        drawn = grid_chart(chart, start, days)
    else:
        drawn = series_chart(chart, color)
    return drawn.configure_view(strokeWidth=0)
