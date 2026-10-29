from collections.abc import Mapping

import streamlit as st

from dotlife.dashboard.cards import Card, Layout, Selection
from dotlife.dashboard.charts import card_chart
from dotlife.dashboard.data import set_listed

COLUMNS = 4
CARD_STYLE = """
<style>
[class*="st-key-card-"] [class*="st-key-menu-"] {
  opacity: 0; transition: opacity 0.15s;
}
[class*="st-key-card-"]:hover [class*="st-key-menu-"],
[class*="st-key-card-"]:focus-within [class*="st-key-menu-"] { opacity: 1; }
@media (hover: none) { [class*="st-key-card-"] [class*="st-key-menu-"] { opacity: 1; } }
</style>
"""


def menu_actions(
    card: Card, layout: Layout, category: str
) -> dict[str, tuple[str, str, bool]]:
    """List what a card's menu offers, given what is already pinned.

    Args:
        card: The card.
        layout: The current pins and hides.
        category: The card's category label, e.g. "Activity".

    Returns:
        Menu text mapped to (list name, key, add or remove).
    """
    name = card.key.split(".")[0]
    card_pinned = card.key in layout.pinned
    category_pinned = name in layout.pinned
    return {
        "Unpin card" if card_pinned else "Pin card to the top": (
            "pinned",
            card.key,
            not card_pinned,
        ),
        f"Unpin all of {category}" if category_pinned else f"Pin all of {category}": (
            "pinned",
            name,
            not category_pinned,
        ),
        "Hide card": ("hidden", card.key, True),
        f"Hide all of {category}": ("hidden", name, True),
    }


def show_card(
    card: Card, selection: Selection, section: str, layout: Layout, category: str
) -> None:
    """Draw one Overview card, with a menu that appears on hover.

    Args:
        card: The card's content.
        selection: The chosen period.
        section: Where it is drawn ("pinned" or an area), to keep widget keys unique.
        layout: The current pins and hides, for the menu.
        category: The card's category label, for the menu.
    """
    period = selection.period.value
    with st.container(border=True, height="stretch", key=f"card-{section}-{card.key}"):
        with st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
        ):
            st.badge(card.chip, color=card.color)
            actions = menu_actions(card, layout, category)
            choice = st.menu_button(
                "",
                list(actions),
                icon=":material/more_horiz:",
                type="tertiary",
                key=f"menu-{section}-{card.key}",
                help="Pin or hide this card",
            )
            if choice is not None:
                set_listed(*actions[choice])
                st.rerun()
        st.metric(
            card.label,
            card.value,
            card.delta,
            delta_color=card.color,
            delta_description=None if card.delta is None else f"vs last {period}",
        )
        if card.chart is not None:
            st.altair_chart(
                card_chart(
                    card.chart,
                    card.color,
                    selection.start,
                    (selection.end - selection.start).days,
                ),
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
    cards: list[Card],
    selection: Selection,
    section: str,
    layout: Layout,
    labels: Mapping[str, str],
) -> None:
    """Draw cards in rows of four.

    Args:
        cards: The cards, in order.
        selection: The chosen period.
        section: The section's name, to keep widget keys unique.
        layout: The current pins and hides.
        labels: Category labels by category name.
    """
    for first in range(0, len(cards), COLUMNS):
        row = cards[first : first + COLUMNS]
        for column, card in zip(st.columns(COLUMNS), row, strict=False):
            with column:
                category = card.key.split(".")[0]
                show_card(
                    card, selection, section, layout, labels.get(category, category)
                )


def show_hidden(
    layout: Layout, labels: Mapping[str, str], card_labels: Mapping[str, str]
) -> None:
    """List hidden cards and categories, each with a button to show it again.

    Args:
        layout: The current pins and hides.
        labels: Category labels by category name.
        card_labels: Card labels by card key.
    """
    if not layout.hidden:
        return
    cards = sum("." in entry for entry in layout.hidden)
    categories = len(layout.hidden) - cards
    parts = [
        f"{cards} card{'' if cards == 1 else 's'}" if cards else "",
        f"{categories} categor{'y' if categories == 1 else 'ies'}"
        if categories
        else "",
    ]
    with st.expander(f"Hidden: {', '.join(part for part in parts if part)}"):
        for entry in layout.hidden:
            name = (
                card_labels.get(entry, entry)
                if "." in entry
                else f"All of {labels.get(entry, entry)}"
            )
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(name)
                st.button(
                    "Show again",
                    key=f"unhide-{entry}",
                    type="tertiary",
                    on_click=set_listed,
                    args=("hidden", entry, False),
                )
