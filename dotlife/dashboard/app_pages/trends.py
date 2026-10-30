from datetime import date, datetime
from typing import cast

import streamlit as st

from dotlife.dashboard.cards import build_trend, trend_specs
from dotlife.dashboard.charts import ALT_TEXT, nights_chart, trend_chart
from dotlife.dashboard.data import dataset, layout, period_title, selection
from dotlife.dashboard.display import hours_minutes
from dotlife.dashboard.widgets import category_menu, show_hidden
from dotlife.periods import Period

HISTORY = {
    "3 months": {Period.WEEK: 13, Period.MONTH: 3},
    "6 months": {Period.WEEK: 26, Period.MONTH: 6},
    "1 year": {Period.WEEK: 52, Period.MONTH: 12},
    "All": {Period.WEEK: None, Period.MONTH: None},
}

data = dataset()
chosen = selection()
arrangement = layout("categories")
categories = [
    category
    for category in data.categories
    if category.metrics
    and category.name != "events"
    and (chosen.show_sensitive or not category.sensitive)
    and category.name not in arrangement.hidden
]
categories.sort(
    key=lambda category: (
        arrangement.pin_rank(category.name) is None,
        arrangement.pin_rank(category.name) or 0,
    )
)

st.title("Trends")
if not categories:
    st.info("No categories with numbers to chart yet.")
else:
    names = [category.name for category in categories]
    labels = {category.name: category.label for category in categories}
    name = st.pills(
        "Category",
        names,
        default="sleep" if "sleep" in names else names[0],
        required=True,
        format_func=lambda option: labels[option],
        key="trend_category",
    )
    category = categories[names.index(cast(str, name))]
    with st.container(horizontal=True, vertical_alignment="bottom"):
        history = st.segmented_control(
            "History",
            list(HISTORY),
            default="6 months",
            required=True,
            key="trend_history",
        )
        category_menu(category.name, category.label, arrangement)
    limit = HISTORY[cast(str, history)][chosen.period]
    events = [
        (cast(date, row["date"]), cast(str, row["label"]))
        for row in data.rows.get("events", [])
    ]

    st.caption(
        f"{chosen.period.value.title()}ly values up to {period_title(chosen).lower()}. "
        "Totals are bars, averages a line over each day's dot, and ratings a "
        "calendar of days. The grey band is your usual range and the green dashed "
        "line your goal. Grey dashed lines are life events: hover for details."
    )

    for spec in trend_specs(category):
        trend = build_trend(spec, data, chosen, limit)
        if trend is None:
            continue
        with st.container(border=True):
            st.subheader(trend.label)
            st.caption(trend.summary)
            for note in trend.notes:
                st.caption(note)
            st.altair_chart(
                trend_chart(trend, events),
                alt=f"{trend.label} by {chosen.period.value}: {ALT_TEXT[trend.kind]}",
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

show_hidden(
    arrangement.hidden,
    {category.name: category.label for category in data.categories},
    "hidden_categories",
    "category/categories",
)
