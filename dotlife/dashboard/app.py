import tomllib
from functools import partial
from pathlib import Path

import streamlit as st

from dotlife.dashboard.data import dataset, keep_period, period_label, period_starts
from dotlife.periods import Period

ASSETS = Path(__file__).resolve().parent / "assets"
CREDIT = """
<style>
.dotlife-credit { margin: 0; font-size: 0.8125rem; opacity: 0.7; }
.dotlife-credit a {
  color: inherit;
  text-decoration: none;
  background: linear-gradient(currentColor, currentColor) 0 100% / 0 1px no-repeat;
  transition: background-size 0.3s ease;
}
.dotlife-credit a:hover,
.dotlife-credit a:focus-visible { background-size: 100% 1px; }
@media (prefers-reduced-motion: reduce) { .dotlife-credit a { transition: none; } }
</style>
<p class="dotlife-credit">Created by
<a href="https://www.flaviaouyang.com" target="_blank" rel="noopener">
Flavia Ouyang</a></p>
"""

st.set_page_config(
    page_title="dotlife", page_icon=str(ASSETS / "favicon.png"), layout="wide"
)
st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "favicon.png"), size="large")

try:
    data = dataset()
except (FileNotFoundError, ValueError, tomllib.TOMLDecodeError) as error:
    st.error(str(error), title="dotlife can't read your data")
    st.stop()

first_day, as_of = data.first_day, data.as_of
if first_day is None or as_of is None:
    st.info("Add data files to your data folder, then reload.", title="No data yet")
    st.stop()

pages = [
    st.Page(
        "app_pages/overview.py",
        title="Overview",
        icon=":material/dashboard:",
        default=True,
    ),
    st.Page("app_pages/trends.py", title="Trends", icon=":material/monitoring:"),
    st.Page(
        "app_pages/reflections.py", title="Reflections", icon=":material/edit_note:"
    ),
    st.Page("app_pages/health.py", title="Data health", icon=":material/fact_check:"),
]
navigation = st.navigation(pages, position="sidebar")

default_period = data.source.config.get("dashboard", {}).get("period", "week")
with st.sidebar:
    period = st.segmented_control(
        "Period",
        [Period.WEEK, Period.MONTH],
        default=Period(default_period),
        required=True,
        format_func=lambda choice: choice.value.title(),
        key="period",
        on_change=keep_period,
        width="stretch",
    )
    st.selectbox(
        "Showing",
        period_starts(first_day, as_of, period),
        format_func=partial(period_label, period=period, as_of=as_of),
        key="start",
    )
    st.toggle(
        "Show sensitive",
        value=data.source.config.get("dashboard", {}).get("show_sensitive", False),
        key="show_sensitive",
        help="Reflections, cycle, medication, symptoms, glucose, finances, social and "
        "travel. Switch off before sharing your screen.",
    )
    if data.source.is_sample:
        st.info(
            "You're looking at Alice, of Alice and Bob: a made-up cryptographer in "
            "London. Add your own data folder and she disappears.",
            title="Sample data",
        )
    st.html(CREDIT)

navigation.run()
