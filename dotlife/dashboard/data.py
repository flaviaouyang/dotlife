import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from dotlife.config import CONFIG_ENV, DATA_ENV, find_data
from dotlife.load import Dataset, load_dataset
from dotlife.periods import Period, period_end, period_start


@dataclass(frozen=True, slots=True)
class Selection:
    """What the sidebar has chosen; every page reads it.

    Attributes:
        period: Weeks or months.
        start: First day of the chosen period.
        show_sensitive: Whether sensitive categories are shown.
    """

    period: Period
    start: date
    show_sensitive: bool

    @property
    def end(self) -> date:
        """The day after the chosen period ends."""
        return period_end(self.start, self.period)


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
