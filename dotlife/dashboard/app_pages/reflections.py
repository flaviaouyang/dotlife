import re
from itertools import groupby
from math import ceil

import streamlit as st

from dotlife.dashboard.data import dataset, selection

MARKDOWN_SPECIALS = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>$~:])")
PAGE_SIZE = 20


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


def turn_page(page: int) -> None:
    """Show another page of entries.

    Args:
        page: The page to show, counting from 0.
    """
    st.session_state.reflections_page = page


def pager(page: int, pages: int, shown: int, place: str) -> None:
    """Show buttons for newer and older entries, when there is more than a page.

    Args:
        page: The page shown, counting from 0.
        pages: How many pages there are.
        shown: How many entries this page shows.
        place: Where the buttons sit ("top" or "bottom"), to keep their keys apart.
    """
    if pages == 1:
        return
    first = page * PAGE_SIZE + 1
    with st.container(
        horizontal=True, horizontal_alignment="center", vertical_alignment="center"
    ):
        st.button(
            "Newer",
            icon=":material/chevron_left:",
            disabled=page == 0,
            on_click=turn_page,
            args=(page - 1,),
            key=f"newer_{place}",
        )
        st.caption(
            f"Page {page + 1} of {pages}: entries {first} to {first + shown - 1}",
            width="content",
        )
        st.button(
            "Older",
            icon=":material/chevron_right:",
            disabled=page == pages - 1,
            on_click=turn_page,
            args=(page + 1,),
            key=f"older_{place}",
        )


data = dataset()
st.title("Reflections")
if not selection().show_sensitive:
    st.info(
        "Reflections are sensitive. Switch on **Show sensitive** in the sidebar to "
        "read them, and switch it off again before sharing your screen.",
        title="Hidden",
    )
elif not data.reflections:
    st.info(
        "Write short reflections in `reflections/2026.txt`, each starting with its "
        "time, like `[2026-03-08 21:30] Long walk after work. #walking`.",
        icon=":material/edit_note:",
    )
else:
    first, last = data.reflections[0].day, data.reflections[-1].day
    with st.container(horizontal=True, vertical_alignment="bottom"):
        query = st.text_input(
            "Search",
            placeholder="Words to find, e.g. tired walk",
            icon=":material/search:",
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
    pages = max(1, ceil(len(hits) / PAGE_SIZE))
    filters = (tuple(words), start, end, tuple(picked))
    if st.session_state.get("reflections_filters") != filters:
        st.session_state.reflections_filters = filters
        st.session_state.reflections_page = 0
    page = min(st.session_state.reflections_page, pages - 1)
    shown = hits[::-1][page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    days = {reflection.day for reflection in hits}
    st.caption(
        f"{len(hits)} of {len(data.reflections)} entries, on {len(days)} "
        f"{'day' if len(days) == 1 else 'days'}. "
        "Every word must match; case is ignored."
    )
    pager(page, pages, len(shown), "top")
    for day, group in groupby(shown, key=lambda r: r.day):
        st.subheader(f"{day:%A, %b} {day.day}, {day.year}", divider="gray")
        for reflection in sorted(group, key=lambda r: r.time):
            with st.container(border=True):
                star = " :material/star:" if reflection.starred else ""
                st.caption(f"{reflection.time:%H:%M}{star}")
                st.markdown(highlighted(reflection.text, words))
    pager(page, pages, len(shown), "bottom")
