from datetime import date

import streamlit as st

from dotlife.dashboard.cards import Card, Selection
from dotlife.dashboard.charts import card_chart
from dotlife.dashboard.data import set_pinned

COLUMNS = 4


def show_card(
    card: Card, period: str, section: str, pinned: bool, start: date, days: int
) -> None:
    """Draw one Overview card: status, pin button, number, change, notes.

    Args:
        card: The card's content.
        period: "week" or "month", for the change's description.
        section: Where it is drawn ("pinned" or an area), to keep widget keys unique.
        pinned: Whether the card is pinned, which sets the button's action.
        start: The selected period's first day.
        days: The selected period's length in days.
    """
    with st.container(border=True, height="stretch"):
        with st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
        ):
            st.badge(card.chip, color=card.color)
            st.button(
                "Pinned" if pinned else "Pin",
                icon=":material/push_pin:",
                type="tertiary",
                key=f"pin-{section}-{card.key}",
                help="Unpin from the top"
                if pinned
                else "Pin to the top of the Overview",
                on_click=set_pinned,
                args=(card.key, not pinned),
            )
        st.metric(
            card.label,
            card.value,
            card.delta,
            delta_color=card.color,
            delta_description=None if card.delta is None else f"vs last {period}",
        )
        if card.chart is not None:
            st.altair_chart(
                card_chart(card.chart, card.color, start, days),
                alt=f"{card.label}: recent values, with the usual range and goal",
            )
        st.caption(
            ". ".join(part for part in (card.unit.capitalize(), card.usual) if part)
        )
        if card.goal:
            st.caption(f":material/flag: {card.goal}")
        if card.note:
            st.caption(card.note)


def show_grid(
    cards: list[Card], selection: Selection, section: str, pinned: set[str]
) -> None:
    """Draw cards in rows of four.

    Args:
        cards: The cards, in order.
        selection: The chosen period.
        section: The section's name, to keep widget keys unique.
        pinned: Keys of the pinned cards.
    """
    for first in range(0, len(cards), COLUMNS):
        row = cards[first : first + COLUMNS]
        for column, card in zip(st.columns(COLUMNS), row, strict=False):
            with column:
                show_card(
                    card,
                    selection.period.value,
                    section,
                    card.key in pinned,
                    selection.start,
                    (selection.end - selection.start).days,
                )
