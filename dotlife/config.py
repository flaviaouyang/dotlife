import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotlife.schema import Category, Context, Metric


def load_config(path: Path) -> dict[str, Any]:
    """Read config.toml.

    Args:
        path: Path to the config file.

    Returns:
        The parsed settings.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        tomllib.TOMLDecodeError: If the file isn't valid TOML.
    """
    with path.open("rb") as file:
        return tomllib.load(file)


def context_for(category: Category, config: Mapping[str, Any]) -> Context:
    """Build the settings a category's plug-ins see.

    Args:
        category: The category.
        config: The whole of config.toml, as returned by `load_config`.

    Returns:
        The user's time zone and the category's config section (empty if absent).

    Raises:
        ValueError: If ``timezone`` is missing or not a known IANA time zone.
    """
    name = config.get("timezone")
    if name is None:
        raise ValueError('config.toml: set timezone, e.g. timezone = "Europe/Berlin"')
    try:
        timezone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(
            f"config.toml: timezone {name!r} is not an IANA time zone name"
        ) from error
    return Context(timezone=timezone, options=config.get(category.name, {}))


def plausible_range(metric: Metric, context: Context) -> tuple[float, float] | None:
    """Return a metric's plausible bounds, preferring the user's override.

    Args:
        metric: The metric.
        context: Its category's settings; ``[<category>.plausible]`` may hold
            ``<column> = [low, high]``.

    Returns:
        The (low, high) bounds, or None when the metric has none.

    Raises:
        ValueError: If the override isn't two numbers with low below high.

    Example:
        >>> from zoneinfo import ZoneInfo
        >>> from dotlife.categories import ACTIVITY
        >>> steps = ACTIVITY.metrics[0]
        >>> context = Context(ZoneInfo("UTC"), {"plausible": {"steps": [0, 150000]}})
        >>> plausible_range(steps, context)
        (0.0, 150000.0)
    """
    override = context.options.get("plausible", {}).get(metric.column)
    if override is None:
        return metric.plausible
    try:
        low, high = (float(bound) for bound in override)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"config.toml: plausible.{metric.column} must be [low, high], "
            f"got {override!r}"
        ) from error
    if low >= high:
        raise ValueError(
            f"config.toml: plausible.{metric.column} low {low} is not below high {high}"
        )
    return low, high


def related_metrics(metric: Metric, context: Context) -> tuple[str, ...]:
    """Return the metrics checked with this one for the stuck flag, preferring config.

    Args:
        metric: The metric.
        context: Its category's settings; ``[<category>.related]`` may hold
            ``<column> = ["category.column", ...]``, where an empty list turns the
            stuck flag off.

    Returns:
        Related metrics as ``category.column`` names.
    """
    override = context.options.get("related", {}).get(metric.column)
    return metric.related if override is None else tuple(override)
