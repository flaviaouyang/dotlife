import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotlife.categories import CATEGORIES
from dotlife.schema import (
    DATE,
    SOURCE,
    Aggregate,
    Category,
    Context,
    Grain,
    Metric,
)

CONFIG_ENV, DATA_ENV = "DOTLIFE_CONFIG", "DOTLIFE_DATA"  # set by `dotlife dashboard`
CUSTOM_NAME = re.compile(r"[a-z][a-z0-9_]*")
BUILT_IN_NAMES = frozenset(category.name for category in CATEGORIES)


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


def custom_category(name: str, spec: Mapping[str, Any]) -> Category:
    """Build a category for a custom metric described in ``[custom.<name>]``.

    Its file is ``<name>.csv`` with the columns ``date``, ``source`` and ``value``.

    Args:
        name: The metric's name, the key under ``custom``.
        spec: Its table: ``label``, ``unit`` and ``summary`` are required;
            ``higher_is_better``, ``minimum``, ``maximum`` and ``plausible`` are
            optional.

    Returns:
        The category.

    Raises:
        ValueError: If the name clashes with a built-in category or isn't
            lower_snake_case, or the table is missing or misusing a key.

    Example:
        >>> spec = {"label": "Guitar practice", "unit": "min", "summary": "sum"}
        >>> custom_category("guitar", spec).file
        'guitar.csv'
    """
    where = f"config.toml: [custom.{name}]"
    if name in BUILT_IN_NAMES:
        raise ValueError(f"{where} has the same name as a built-in category")
    if CUSTOM_NAME.fullmatch(name) is None:
        raise ValueError(f"{where}: use lower_snake_case names, e.g. guitar_practice")
    missing = [key for key in ("label", "unit", "summary") if key not in spec]
    if missing:
        raise ValueError(f"{where} is missing {', '.join(missing)}")
    try:
        summary = Aggregate(spec["summary"])
    except ValueError as error:
        choices = ", ".join(aggregate.value for aggregate in Aggregate)
        raise ValueError(f"{where}: summary must be one of {choices}") from error
    plausible = spec.get("plausible")
    metric = Metric(
        column="value",
        label=spec["label"],
        unit=spec["unit"],
        aggregate=summary,
        higher_is_better=spec.get("higher_is_better"),
        minimum=spec.get("minimum"),
        maximum=spec.get("maximum"),
        plausible=None if plausible is None else (plausible[0], plausible[1]),
    )
    return Category(
        name=name,
        label=spec["label"],
        file=f"{name}.csv",
        grain=Grain.DAY,
        fields=(DATE, SOURCE),
        metrics=(metric,),
    )


def all_categories(config: Mapping[str, Any]) -> tuple[Category, ...]:
    """Return the built-in categories followed by the user's custom metrics.

    Args:
        config: The whole of config.toml.

    Returns:
        Every category dotlife knows about for this config.

    Raises:
        ValueError: If a custom metric is described wrongly.
    """
    custom = config.get("custom", {})
    return CATEGORIES + tuple(
        custom_category(name, spec) for name, spec in custom.items()
    )


@dataclass(frozen=True, slots=True)
class DataSource:
    """The data folder to read and the settings that go with it.

    Attributes:
        folder: The data folder.
        config: The settings: the folder's own config.toml if it has one (as
            ``sample/`` does), else the repo's.
        is_sample: Whether this is the sample data, used because ``data_dir`` is
            missing.
    """

    folder: Path
    config: dict[str, Any]
    is_sample: bool = False


def find_data(config_path: Path, folder: Path | None = None) -> DataSource:
    """Pick the data folder and its settings.

    The folder is the one given, else ``data_dir`` from config.toml, else
    ``sample/`` next to config.toml. A config.toml inside the folder wins over the
    repo's, so the sample keeps its own time zone whatever the user's is.

    Args:
        config_path: Path to the repo's config.toml.
        folder: A folder given on the command line, or None.

    Returns:
        The folder and its settings.

    Raises:
        FileNotFoundError: If the folder, or a config file it needs, doesn't exist.
        tomllib.TOMLDecodeError: If a config file isn't valid TOML.
    """
    chosen = folder
    if chosen is None:
        repo_config = load_config(config_path)
        chosen = config_path.parent / repo_config.get("data_dir", "data")
    is_sample = folder is None and not chosen.is_dir()
    if is_sample:
        chosen = config_path.parent / "sample"
    if not chosen.is_dir():
        raise FileNotFoundError(f"{chosen} is not a folder")
    own_config = chosen / "config.toml"
    config_file = own_config if own_config.is_file() else config_path
    return DataSource(chosen, load_config(config_file), is_sample)
