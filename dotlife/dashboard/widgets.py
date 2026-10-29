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


def apply_choice(
    choice: str | None, actions: Mapping[str, tuple[str, str, bool]]
) -> None:
    """Save a menu choice to config.toml and redraw the page.

    Args:
        choice: The chosen menu item, or None when nothing was chosen.
        actions: Menu text mapped to (list name, key, add or remove).
    """
    if choice is None:
        return
    set_listed(*actions[choice])
    st.rerun()


def card_actions(card: Card, layout: Layout) -> dict[str, tuple[str, str, bool]]:
    """List what an Overview card's menu offers.

    Args:
        card: The card.
        layout: The Overview's pins and hides.

    Returns:
        Menu text mapped to (list name, key, add or remove).
    """
    pinned = card.key in layout.pinned
    return {
        "Unpin card" if pinned else "Pin card to the top": (
            "pinned_cards",
            card.key,
            not pinned,
        ),
        "Hide card": ("hidden_cards", card.key, True),
    }


def category_menu(name: str, label: str, layout: Layout) -> None:
    """Draw the Trends menu that pins or hides the category on show.

    Args:
        name: The category's name.
        label: The category's label, e.g. "Sleep".
        layout: The Trends pins and hides.
    """
    pinned = name in layout.pinned
    actions = {
        f"Unpin {label}" if pinned else f"Pin {label} to the front": (
            "pinned_categories",
            name,
            not pinned,
        ),
        f"Hide {label}": ("hidden_categories", name, True),
    }
    choice = st.menu_button(
        "",
        list(actions),
        icon=":material/more_horiz:",
        type="tertiary",
        key=f"category-menu-{name}",
        help=f"Pin or hide {label}",
    )
    apply_choice(choice, actions)


def show_card(card: Card, selection: Selection, section: str, layout: Layout) -> None:
    """Draw one Overview card, with a menu that appears on hover.

    Args:
        card: The card's content.
        selection: The chosen period.
        section: Where it is drawn ("pinned" or an area), to keep widget keys unique.
        layout: The Overview's pins and hides, for the menu.
    """
    period = selection.period.value
    with st.container(border=True, height="stretch", key=f"card-{section}-{card.key}"):
        with st.container(
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
        ):
            st.badge(card.chip, color=card.color)
            actions = card_actions(card, layout)
            choice = st.menu_button(
                "",
                list(actions),
                icon=":material/more_horiz:",
                type="tertiary",
                key=f"menu-{section}-{card.key}",
                help="Pin or hide this card",
            )
            apply_choice(choice, actions)
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
    cards: list[Card], selection: Selection, section: str, layout: Layout
) -> None:
    """Draw cards in rows of four.

    Args:
        cards: The cards, in order.
        selection: The chosen period.
        section: The section's name, to keep widget keys unique.
        layout: The Overview's pins and hides.
    """
    for first in range(0, len(cards), COLUMNS):
        row = cards[first : first + COLUMNS]
        for column, card in zip(st.columns(COLUMNS), row, strict=False):
            with column:
                show_card(card, selection, section, layout)


def show_hidden(
    hidden: tuple[str, ...], labels: Mapping[str, str], list_name: str, noun: str
) -> None:
    """List hidden cards or categories, each with a button to show it again.

    Args:
        hidden: The hidden keys.
        labels: Labels by key.
        list_name: The config list they live in, e.g. ``hidden_cards``.
        noun: What they are, singular and plural, e.g. ``card/cards``.
    """
    if not hidden:
        return
    one, many = noun.split("/")
    with st.expander(f"Hidden: {len(hidden)} {one if len(hidden) == 1 else many}"):
        for key in hidden:
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(labels.get(key, key))
                st.button(
                    "Show again",
                    key=f"unhide-{list_name}-{key}",
                    type="tertiary",
                    on_click=set_listed,
                    args=(list_name, key, False),
                )
