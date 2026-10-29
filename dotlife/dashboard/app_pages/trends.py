from datetime import date, datetime
from typing import cast

import streamlit as st

from dotlife.dashboard.cards import read, trend_specs
from dotlife.dashboard.charts import nights_chart, trend_chart
from dotlife.dashboard.data import dataset, period_title, selection
from dotlife.dashboard.display import format_value, hours_minutes
from dotlife.periods import Period

HISTORY = {
    "3 months": {Period.WEEK: 13, Period.MONTH: 3},
    "6 months": {Period.WEEK: 26, Period.MONTH: 6},
    "1 year": {Period.WEEK: 52, Period.MONTH: 12},
    "All": {Period.WEEK: None, Period.MONTH: None},
}

data = dataset()
chosen = selection()
categories = [
    category
    for category in data.categories
    if category.metrics
    and category.name != "events"
    and (chosen.show_sensitive or not category.sensitive)
]

st.title("Trends")
if not categories:
    st.info("No categories with numbers to chart yet.")
    st.stop()

names = [category.name for category in categories]
labels = {category.name: category.label for category in categories}
with st.container(horizontal=True, vertical_alignment="bottom"):
    name = st.pills(
        "Category",
        names,
        default="sleep" if "sleep" in names else names[0],
        required=True,
        format_func=lambda option: labels[option],
        key="trend_category",
    )
    history = st.segmented_control(
        "History", list(HISTORY), default="6 months", required=True, key="trend_history"
    )
category = categories[names.index(cast(str, name))]
limit = HISTORY[cast(str, history)][chosen.period]
events = [
    (cast(date, row["date"]), cast(str, row["label"]))
    for row in data.rows.get("events", [])
]

st.caption(
    f"{chosen.period.value.title()}ly values up to {period_title(chosen).lower()}. "
    "The band is your usual range. Dashed lines are life events: hover for details."
)

for spec in trend_specs(category):
    reading = read(spec, data, chosen)
    if reading is None:
        continue
    points = sorted(
        (start, value)
        for start, value in reading.values.items()
        if start <= chosen.start
    )
    points = points if limit is None else points[-limit:]
    shown = [event for event in events if event[0] >= points[0][0]]
    with st.container(border=True):
        st.subheader(spec.label)
        current = format_value(reading.current, reading.unit)
        usual = (
            ""
            if reading.usual is None
            else f" · usual {format_value(reading.usual.low, reading.unit)} to "
            f"{format_value(reading.usual.high, reading.unit)}"
        )
        st.caption(f"This {chosen.period.value}: {current}{usual}")
        if reading.stale_since is not None:
            changed = reading.stale_since
            st.caption(
                f"Unchanged since {changed.day} {changed:%b %Y}, so it may be stale: "
                "the readings are shown, but it isn't compared with its usual range."
            )
        st.altair_chart(
            trend_chart(points, reading.unit, reading.usual, shown),
            alt=f"{spec.label} by {chosen.period.value}, with its usual range",
        )

if category.name == "sleep" and chosen.period is Period.WEEK:
    timezone = data.contexts["sleep"].timezone
    nights = sorted(
        (
            cast(date, row["date"]),
            cast(datetime, row["start"]).astimezone(timezone),
            cast(datetime, row["end"]).astimezone(timezone),
            row.get("asleep_min"),
        )
        for row in data.rows["sleep"]
        if chosen.start <= cast(date, row["date"]) < chosen.end
    )
    if nights:
        with st.container(border=True):
            st.subheader(f"This {chosen.period.value}'s nights")
            st.caption("Each night is filed under the day you woke up.")
            st.altair_chart(
                nights_chart(
                    [
                        (
                            f"{day:%a} {day.day}",
                            bed,
                            wake,
                            ""
                            if asleep is None
                            else hours_minutes(cast(float, asleep)),
                        )
                        for day, bed, wake, asleep in nights
                    ]
                ),
                alt="Bars from bedtime to wake-up for each night of the week",
            )
