import re
from collections import Counter
from datetime import date
from itertools import groupby

import polars as pl
import streamlit as st

from dotlife.dashboard.data import dataset, selection
from dotlife.dashboard.display import hours_minutes, number
from dotlife.load import Dataset
from dotlife.summaries import Daily, daily_values

DAYS_SHOWN = 20
MARKDOWN_SPECIALS = re.compile(r"([\\`*_{}\[\]()#+\-.!|>~<])")


def day_values(data: Dataset, category_name: str, column: str) -> Daily:
    """Return a metric's daily values, or nothing when the category has no data.

    Args:
        data: The loaded data.
        category_name: The category.
        column: The metric.

    Returns:
        Values by date.
    """
    category = next((c for c in data.categories if c.name == category_name), None)
    if category is None:
        return {}
    context = data.contexts[category_name]
    return daily_values(category, data.rows[category_name], column, context)


def day_context(day: date, steps: Daily, asleep: Daily, mood: Daily) -> str:
    """Describe what the data says about a day, next to what was written that day.

    Args:
        day: The date.
        steps: Steps by date.
        asleep: Minutes asleep by wake date.
        mood: Mood by date.

    Returns:
        E.g. "11,010 steps · slept 6 h 26 m · mood 4", or empty.
    """
    parts = [
        f"{number(steps[day])} steps" if day in steps else "",
        f"slept {hours_minutes(asleep[day])}" if day in asleep else "",
        f"mood {number(mood[day])}" if day in mood else "",
    ]
    return " · ".join(part for part in parts if part)


def as_plain_markdown(text: str) -> str:
    """Show plain text through Markdown unchanged: escape symbols, keep line breaks.

    Args:
        text: A reflection's text.

    Returns:
        Markdown that renders as the original text.
    """
    return "  \n".join(
        MARKDOWN_SPECIALS.sub(r"\\\1", line) for line in text.split("\n")
    )


data = dataset()
chosen = selection()
st.title("Reflections")
if not chosen.show_sensitive:
    st.info(
        "Reflections are sensitive. Switch on **Show sensitive** in the sidebar to "
        "read them, and switch it off again before sharing your screen.",
        title="Hidden",
    )
    st.stop()
if not data.reflections:
    st.info(
        "Write short reflections in `reflections/2026.txt`, one a line, each starting "
        "with its time, like `[2026-03-08 21:30] Long walk after work. #walking`.",
        title="No reflections yet",
    )
    st.stop()

tag_counts = Counter(tag for reflection in data.reflections for tag in reflection.tags)
entries_column, summary_column = st.columns([3, 1], gap="large")
with entries_column:
    query = st.text_input("Search reflections", placeholder="A word or phrase")
    tags = st.pills(
        "Tags",
        [tag for tag, _ in tag_counts.most_common()],
        selection_mode="multi",
        format_func=lambda tag: f"{tag} {tag_counts[tag]}",
        key="reflection_tags",
    )
    matches = [
        reflection
        for reflection in reversed(data.reflections)
        if reflection.day < chosen.end
        and query.lower() in reflection.text.lower()
        and set(tags) <= set(reflection.tags)
    ]
    days = [(day, list(group)) for day, group in groupby(matches, key=lambda r: r.day)]
    st.caption(
        f"{len(matches)} reflections on {len(days)} days, up to the end of the chosen "
        f"{chosen.period.value}, newest first."
        + (
            f" The latest {DAYS_SHOWN} days are shown."
            if len(days) > DAYS_SHOWN
            else ""
        )
    )
    steps = day_values(data, "activity", "steps")
    asleep = day_values(data, "sleep", "asleep_min")
    mood = day_values(data, "mood", "mood")
    for day, reflections in days[:DAYS_SHOWN]:
        with st.container(border=True):
            st.markdown(f"**{day:%a} {day.day} {day:%b %Y}**")
            context = day_context(day, steps, asleep, mood)
            if context:
                st.caption(context)
            for reflection in sorted(reflections, key=lambda r: r.time):
                star = " :material/star:" if reflection.starred else ""
                st.markdown(
                    f":gray[{reflection.time:%H:%M}]{star} "
                    f"{as_plain_markdown(reflection.text)}"
                )

with summary_column:
    st.subheader("Reflections a month")
    months = Counter(reflection.day.replace(day=1) for reflection in data.reflections)
    frame = pl.DataFrame(
        {
            "month": [f"{month:%b %Y}" for month in sorted(months)],
            "reflections": [months[month] for month in sorted(months)],
        }
    )
    st.bar_chart(
        frame,
        x="month",
        y="reflections",
        horizontal=True,
        sort=False,
        x_label="",
        y_label="",
        height=40 * len(months) + 40,
        alt="Number of reflections written in each month",
    )
    st.caption(
        "One text file a year in `reflections/`. Days without a reflection are not "
        f"gaps. {len(data.reflections)} reflections in all."
    )
