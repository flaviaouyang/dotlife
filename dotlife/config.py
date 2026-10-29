import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotlife.schema import Category, Context


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
