import re
from itertools import groupby

import streamlit as st

from dotlife.dashboard.data import dataset, selection

MARKDOWN_SPECIALS = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>$~:])")


def literal(text: str) -> str:
    """Show plain text through Markdown as written: no bold, links, maths or directives.

    Args:
        text: Plain text.

    Returns:
        Markdown that renders as the text, line breaks kept.
    """
    return MARKDOWN_SPECIALS.sub(r"\\\1", text).replace("\n", "  \n")


def highlighted(text: str, words: list[str]) -> str:
    """Show a reflection with every search word marked.

    Args:
        text: The reflection.
        words: Lower-case search words; none means nothing is marked.

    Returns:
        Markdown with each match on an orange background.
    """
    if not words:
        return literal(text)
    pattern = re.compile("|".join(re.escape(word) for word in words), re.IGNORECASE)
    parts, start = [], 0
    for match in pattern.finditer(text):
        parts += [
            literal(text[start : match.start()]),
            f":orange-background[{literal(match[0])}]",
        ]
        start = match.end()
    return "".join(parts) + literal(text[start:])


data = dataset()
st.title("Reflections")
if not selection().show_sensitive:
    st.info(
        "Reflections are sensitive. Switch on **Show sensitive** in the sidebar to "
        "read them, and switch it off again before sharing your screen.",
        title="Hidden",
    )
    st.stop()
if not data.reflections:
    st.info(
        "Write short reflections in `reflections/2026.txt`, each starting with its "
        "time, like `[2026-03-08 21:30] Long walk after work. #walking`.",
        icon=":material/edit_note:",
    )
    st.stop()

first, last = data.reflections[0].day, data.reflections[-1].day
with st.container(horizontal=True, vertical_alignment="bottom"):
    query = st.text_input(
        "Search", placeholder="Words to find, e.g. tired walk", icon=":material/search:"
    )
    period = st.date_input(
        "Dates", (first, last), min_value=first, max_value=last, width=260
    )
tags = sorted({tag for reflection in data.reflections for tag in reflection.tags})
picked = (
    st.pills("Tags", tags, selection_mode="multi", label_visibility="collapsed")
    if tags
    else []
)

words = query.lower().split()
start, end = (period[0], period[1]) if len(period) == 2 else (first, last)
hits = [
    reflection
    for reflection in data.reflections
    if start <= reflection.day <= end
    and all(word in reflection.text.lower() for word in words)
    and set(picked) <= set(reflection.tags)
]
days = [
    (day, list(group)) for day, group in groupby(reversed(hits), key=lambda r: r.day)
]
st.caption(
    f"{len(hits)} of {len(data.reflections)} entries, on {len(days)} "
    f"{'day' if len(days) == 1 else 'days'}. Every word must match; case is ignored."
)
for day, reflections in days:
    st.subheader(f"{day:%A, %b} {day.day}, {day.year}", divider="gray")
    for reflection in sorted(reflections, key=lambda r: r.time):
        with st.container(border=True):
            star = " :material/star:" if reflection.starred else ""
            st.caption(f"{reflection.time:%H:%M}{star}")
            st.markdown(highlighted(reflection.text, words))
