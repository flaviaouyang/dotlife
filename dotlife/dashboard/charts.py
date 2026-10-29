from collections.abc import Sequence
from datetime import date, datetime

import altair as alt
import polars as pl

from dotlife.dashboard.display import CLOCK
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
) -> alt.LayerChart:
    """Draw a metric's period values with its usual range and life events.

    Args:
        points: (period start, value) pairs, oldest first.
        unit: The display unit, for axis labels.
        usual: The usual range for the latest period, drawn as a band, or None.
        events: (date, label) life events inside the chart's range.

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
