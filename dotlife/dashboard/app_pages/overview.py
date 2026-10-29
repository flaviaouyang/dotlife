import streamlit as st

from dotlife.dashboard.cards import build_overview, usual_periods
from dotlife.dashboard.data import dataset, period_title, selection
from dotlife.dashboard.display import AREAS

COLUMNS = 4

data = dataset()
chosen = selection()
overview = build_overview(data, chosen)
period = chosen.period.value
count = usual_periods(data.source.config, chosen.period)

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

for area in AREAS:
    cards = [card for card in overview.cards if card.area == area]
    if not cards:
        continue
    st.subheader(area)
    for first in range(0, len(cards), COLUMNS):
        for column, card in zip(
            st.columns(COLUMNS), cards[first : first + COLUMNS], strict=False
        ):
            with column.container(border=True, height="stretch"):
                st.badge(card.chip, color=card.color)
                st.metric(
                    card.label,
                    card.value,
                    card.delta,
                    delta_color=card.color,
                    delta_description=None
                    if card.delta is None
                    else f"vs last {period}",
                    chart_data=card.series,
                    chart_type="line",
                )
                st.caption(
                    ". ".join(
                        part for part in (card.unit.capitalize(), card.usual) if part
                    )
                )
                if card.note:
                    st.caption(card.note)

if overview.missing:
    st.caption(f"No data this {period}: {', '.join(overview.missing)}.")
if overview.hidden:
    st.caption(
        f"{overview.hidden} sensitive categories are hidden. Switch on "
        "**Show sensitive** in the sidebar to see them."
    )
