import streamlit as st

from dotlife.dashboard.cards import build_overview, card_labels, usual_periods
from dotlife.dashboard.data import dataset, layout, period_title, selection
from dotlife.dashboard.display import AREAS
from dotlife.dashboard.widgets import CARD_STYLE, show_grid, show_hidden

data = dataset()
chosen = selection()
arrangement = layout("cards")
overview = build_overview(data, chosen, arrangement)
period = chosen.period.value
count = usual_periods(data.source.config, chosen.period)
st.html(CARD_STYLE)

st.title(period_title(chosen))
st.caption(
    f"Each card compares this {period} with the last one and with your usual range: "
    f"the middle half of your last {count} {period}s."
)

if overview.notable:
    with st.container(border=True):
        st.subheader(f"Notable this {period}")
        for card in overview.notable:
            st.markdown(
                f":{card.color}-badge[{card.chip}] **{card.label} {card.value}** "
                f"{card.unit}. {card.usual}."
            )

pinned_cards = sorted(
    (card for card in overview.cards if arrangement.pin_rank(card.key) is not None),
    key=lambda card: arrangement.pin_rank(card.key) or 0,
)
if pinned_cards:
    st.subheader("Pinned")
    show_grid(pinned_cards, chosen, "pinned", arrangement)

for area in AREAS:
    cards = [card for card in overview.cards if card.area == area]
    if cards:
        st.subheader(area)
        show_grid(cards, chosen, area, arrangement)

if overview.missing:
    st.caption(f"No data this {period}: {', '.join(overview.missing)}.")
if overview.hidden:
    st.caption(
        f"{overview.hidden} sensitive categories are hidden. Switch on "
        "**Show sensitive** in the sidebar to see them."
    )
if not pinned_cards:
    st.caption(
        "Use a card's menu to pin it to the top or hide it. Your choices are saved "
        "in config.toml."
    )
show_hidden(arrangement.hidden, card_labels(data), "hidden_cards", "card/cards")
