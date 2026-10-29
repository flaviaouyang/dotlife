from collections import Counter
from datetime import date

import polars as pl
import streamlit as st

from dotlife.dashboard.cards import Selection
from dotlife.dashboard.data import dataset, selection
from dotlife.dashboard.display import hours_minutes, number
from dotlife.load import Dataset
from dotlife.summaries import Daily, daily_values

SHOWN = 20


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
    """Describe what the data says about a day, for the entry written that day.

    Args:
        day: The entry's date.
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


data = dataset()
chosen: Selection = selection()
st.title("Journal")
if not chosen.show_sensitive:
    st.info(
        "The journal is sensitive. Switch on **Show sensitive** in the sidebar to "
        "read it, and switch it off again before sharing your screen.",
        title="Hidden",
    )
    st.stop()
if not data.journal:
    st.info(
        "Add one Markdown file a day to `journal/`, named like `2026-03-08.md`.",
        title="No journal yet",
    )
    st.stop()

tag_counts = Counter(tag for entry in data.journal for tag in entry.tags)
entries_column, summary_column = st.columns([3, 1], gap="large")
with entries_column:
    query = st.text_input("Search entries", placeholder="A word or phrase")
    tags = st.pills(
        "Tags",
        [tag for tag, _ in tag_counts.most_common()],
        selection_mode="multi",
        format_func=lambda tag: f"{tag} {tag_counts[tag]}",
        key="journal_tags",
    )
    matches = [
        entry
        for entry in reversed(data.journal)
        if entry.day < chosen.end
        and query.lower() in entry.text.lower()
        and set(tags) <= set(entry.tags)
    ]
    st.caption(
        f"{len(matches)} entries up to the end of the chosen {chosen.period.value}, "
        "newest first."
        if len(matches) <= SHOWN
        else f"{len(matches)} entries match; the newest {SHOWN} are shown."
    )
    steps = day_values(data, "activity", "steps")
    asleep = day_values(data, "sleep", "asleep_min")
    mood = day_values(data, "mood", "mood")
    for entry in matches[:SHOWN]:
        with st.container(border=True):
            st.markdown(f"**{entry.day:%a} {entry.day.day} {entry.day:%b %Y}**")
            context = day_context(entry.day, steps, asleep, mood)
            if context:
                st.caption(context)
            st.markdown(entry.plain_text)
            if entry.tags:
                st.markdown(" ".join(f":gray-badge[{tag}]" for tag in entry.tags))

with summary_column:
    st.subheader("Entries a month")
    months = Counter(entry.day.replace(day=1) for entry in data.journal)
    frame = pl.DataFrame(
        {
            "month": [f"{month:%b %Y}" for month in sorted(months)],
            "entries": [months[month] for month in sorted(months)],
        }
    )
    st.bar_chart(
        frame,
        x="month",
        y="entries",
        horizontal=True,
        sort=False,
        x_label="",
        y_label="",
        height=40 * len(months) + 40,
        alt="Number of journal entries in each month",
    )
    st.caption(
        "Days without an entry are not gaps. Words starting with # are tags. "
        f"{len(data.journal)} entries in all."
    )
