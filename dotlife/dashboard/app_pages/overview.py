import streamlit as st

from dotlife.dashboard.cards import build_overview, usual_periods
from dotlife.dashboard.data import dataset, period_title, pinned_keys, selection
from dotlife.dashboard.display import AREAS
from dotlife.dashboard.widgets import show_grid

data = dataset()
chosen = selection()
overview = build_overview(data, chosen)
period = chosen.period.value
count = usual_periods(data.source.config, chosen.period)
pins = pinned_keys()
by_key = {card.key: card for card in overview.cards}

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

pinned_cards = [by_key[key] for key in pins if key in by_key]
if pinned_cards:
    st.subheader("Pinned")
    show_grid(pinned_cards, period, "pinned", set(pins))

for area in AREAS:
    cards = [card for card in overview.cards if card.area == area]
    if cards:
        st.subheader(area)
        show_grid(cards, period, area, set(pins))

if overview.missing:
    st.caption(f"No data this {period}: {', '.join(overview.missing)}.")
if overview.hidden:
    st.caption(
        f"{overview.hidden} sensitive categories are hidden. Switch on "
        "**Show sensitive** in the sidebar to see them."
    )
if not pinned_cards:
    st.caption("Pin a card to keep it at the top. Pins are saved in your config.toml.")
