import os
import tomllib
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
import tomlkit

from dotlife.config import CONFIG_ENV, DATA_ENV, find_data
from dotlife.dashboard.cards import Layout, Selection
from dotlife.load import Dataset, load_dataset
from dotlife.periods import Period, period_end, period_start
from dotlife.validate import Report, validate_folder


def folder_signature(folder: Path) -> tuple[tuple[str, float], ...]:
    """Fingerprint a folder by its files' modification times.

    Args:
        folder: The data folder.

    Returns:
        (path, mtime) pairs; any change to a file changes the result.
    """
    return tuple(
        sorted(
            (str(path), path.stat().st_mtime)
            for path in folder.rglob("*")
            if path.is_file()
        )
    )


@st.cache_resource(max_entries=2, show_spinner="Reading your data...")
def cached_dataset(
    config_path: str, data_dir: str | None, signature: tuple[tuple[str, float], ...]
) -> Dataset:
    """Load and cache the dataset; a new signature loads it again.

    Args:
        config_path: Path to the repo's config.toml.
        data_dir: The data folder given on the command line, or None.
        signature: The folder's fingerprint, part of the cache key only.

    Returns:
        The dataset.
    """
    folder = None if data_dir is None else Path(data_dir)
    return load_dataset(find_data(Path(config_path), folder))


def dataset() -> Dataset:
    """Return the dataset for the folder ``dotlife dashboard`` was started with.

    Returns:
        The dataset, reloaded whenever a data file changes.

    Raises:
        FileNotFoundError: If no data folder or config file can be found.
        ValueError: If config.toml has a mistake.
    """
    config_path = os.environ.get(CONFIG_ENV, "config.toml")
    data_dir = os.environ.get(DATA_ENV)
    source = find_data(Path(config_path), None if data_dir is None else Path(data_dir))
    return cached_dataset(config_path, data_dir, folder_signature(source.folder))


@st.cache_resource(max_entries=2, show_spinner="Checking your data...")
def cached_report(
    config_path: str, data_dir: str | None, signature: tuple[tuple[str, float], ...]
) -> Report:
    """Validate and cache the data folder; a new signature validates it again.

    Args:
        config_path: Path to the repo's config.toml.
        data_dir: The data folder given on the command line, or None.
        signature: The folder's fingerprint, part of the cache key only.

    Returns:
        The validator's report.
    """
    folder = None if data_dir is None else Path(data_dir)
    source = find_data(Path(config_path), folder)
    return validate_folder(source.folder, source.config)


def report() -> Report:
    """Return the validator's report for the folder the dashboard shows.

    Returns:
        The report, rechecked whenever a data file changes.
    """
    config_path = os.environ.get(CONFIG_ENV, "config.toml")
    data_dir = os.environ.get(DATA_ENV)
    source = find_data(Path(config_path), None if data_dir is None else Path(data_dir))
    return cached_report(config_path, data_dir, folder_signature(source.folder))


def period_starts(first: date, last: date, period: Period) -> list[date]:
    """List the first days of every period from one date to another, latest first.

    Args:
        first: The earliest date with data.
        last: The latest date with data.
        period: Weeks or months.

    Returns:
        Period start dates, newest first.
    """
    starts = []
    start = period_start(first, period)
    while start <= last:
        starts.append(start)
        start = period_end(start, period)
    return starts[::-1]


def period_label(start: date, period: Period, as_of: date) -> str:
    """Name a period for people, marking the one still in progress.

    Args:
        start: The period's first day.
        period: Weeks or months.
        as_of: The latest date with data.

    Returns:
        E.g. ``24 to 30 Aug 2026`` or ``August 2026 (so far)``.
    """
    last_day = period_end(start, period) - timedelta(days=1)
    name = (
        f"{start:%B %Y}"
        if period is Period.MONTH
        else f"{start.day} {start:%b} to {last_day.day} {last_day:%b %Y}"
    )
    return f"{name} (so far)" if as_of < last_day else name


def selection() -> Selection:
    """Read the sidebar's choices from session state.

    Returns:
        The current selection.
    """
    state = st.session_state
    return Selection(Period(state["period"]), state["start"], state["show_sensitive"])


def keep_period() -> None:
    """Move the chosen date to the start of its period after the period changes.

    Switching from a week to months then shows the month that holds that week.
    """
    state = st.session_state
    if "start" in state:
        state["start"] = period_start(state["start"], Period(state["period"]))


def period_title(chosen: Selection) -> str:
    """Name the chosen period for a page title.

    Args:
        chosen: The sidebar selection.

    Returns:
        E.g. ``Week of 24 August 2026`` or ``August 2026``.
    """
    if chosen.period is Period.MONTH:
        return f"{chosen.start:%B %Y}"
    return f"Week of {chosen.start.day} {chosen.start:%B %Y}"


def config_path() -> Path:
    """Return the repo's config.toml, which ``dotlife dashboard`` was started with.

    Returns:
        Its path.
    """
    return Path(os.environ.get(CONFIG_ENV, "config.toml"))


def layout() -> Layout:
    """Read the pinned and hidden cards from the repo's config.toml.

    They always live in the repo's own config, even while the sample is shown,
    so pinning or hiding never edits the sample.

    Returns:
        The layout; empty when config.toml can't be read.
    """
    try:
        with config_path().open("rb") as file:
            dashboard = tomllib.load(file).get("dashboard", {})
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return Layout()
    return Layout(
        tuple(dashboard.get("pinned", [])), tuple(dashboard.get("hidden", []))
    )


def set_listed(name: str, key: str, listed: bool) -> None:
    """Add a card or category to, or remove it from, ``pinned`` or ``hidden``.

    The rest of config.toml, comments included, is kept as it is.

    Args:
        name: ``pinned`` or ``hidden``.
        key: A card key such as ``activity.steps``, or a category name.
        listed: True to add it, False to remove it.
    """
    path = config_path()
    with path.open(encoding="utf-8") as file:
        document = tomlkit.parse(file.read())
    dashboard = document.setdefault("dashboard", tomlkit.table())
    keys = [str(item) for item in dashboard.get(name, [])]
    if listed and key not in keys:
        keys.append(key)
    if not listed:
        keys = [entry for entry in keys if entry != key]
    dashboard[name] = keys
    with path.open("w", encoding="utf-8") as file:
        file.write(tomlkit.dumps(document))
