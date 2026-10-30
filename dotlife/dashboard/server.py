from pathlib import Path

# dotlife doesn't use pandas, but Streamlit loads it on first use (st.dataframe on
# Data health) inside a page's thread, while Altair picks it up from sys.modules in
# another. Clicking to another page during that first, slow import showed
# "partially initialized module 'pandas'" errors, so load it once at start-up.
import pandas  # noqa: F401
import streamlit as st
from starlette.requests import Request
from starlette.responses import FileResponse
from starlette.routing import Route

HERE = Path(__file__).resolve().parent
FAVICON = HERE / "assets" / "favicon.png"
ICON_PATHS = ("/favicon.png", "/favicon.ico", "/apple-touch-icon.png")


async def favicon(request: Request) -> FileResponse:
    """Serve dotlife's icon where browsers look for it before any script runs.

    Streamlit's page links ``/favicon.png`` in its HTML and swaps in the app's icon
    later with JavaScript, which Safari ignores. Serving dotlife's icon at the
    original paths makes every browser show it.

    Args:
        request: The incoming request; unused.

    Returns:
        The icon file.
    """
    return FileResponse(FAVICON, media_type="image/png")


app = st.App(str(HERE / "app.py"), routes=[Route(path, favicon) for path in ICON_PATHS])
