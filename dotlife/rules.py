from datetime import date, datetime
from typing import cast

from dotlife.schema import Context, Row, inferred_from


def local_date(row: Row, column: str, context: Context) -> date:
    """Return the user's local date of a timestamp column.

    Args:
        row: A parsed row.
        column: Name of a timestamp column in the row.
        context: Supplies the user's time zone, which handles DST and timestamps
            recorded with another UTC offset.

    Returns:
        The local date.
    """
    return cast(datetime, row[column]).astimezone(context.timezone).date()


def end_after_start(row: Row, context: Context) -> str | None:
    """A session must end after it starts.

    Args:
        row: A parsed row with ``start`` and ``end`` timestamps.
        context: Unused; part of the check signature.

    Returns:
        A problem description, or None when the row is fine.
    """
    start, end = cast(datetime, row["start"]), cast(datetime, row["end"])
    if end > start:
        return None
    return f"end {end.isoformat()} is not after start {start.isoformat()}"


def date_is_wake_date(row: Row, context: Context) -> str | None:
    """A sleep session is filed under the local date its sleeper woke up.

    Args:
        row: A parsed row with ``date`` and an ``end`` timestamp.
        context: Supplies the user's time zone.

    Returns:
        A problem description, or None when the row is fine.
    """
    wake_date = local_date(row, "end", context)
    if row["date"] == wake_date:
        return None
    return (
        f"date {row['date']} should be the wake date {wake_date}: "
        "a night counts toward the day you woke up"
    )


def date_is_start_date(row: Row, context: Context) -> str | None:
    """A session is filed under the local date it started.

    Args:
        row: A parsed row with ``date`` and a ``start`` timestamp.
        context: Supplies the user's time zone.

    Returns:
        A problem description, or None when the row is fine.
    """
    start_date = local_date(row, "start", context)
    if row["date"] == start_date:
        return None
    return f"date {row['date']} should be the start date {start_date}"


def currency_is_home(row: Row, context: Context) -> str | None:
    """Amounts in a currency other than ``home_currency`` are flagged, not converted.

    Args:
        row: A parsed transaction row with ``currency``.
        context: Supplies ``home_currency``; without it nothing is flagged.

    Returns:
        A warning, or None when the row is in the home currency.
    """
    home = context.options.get("home_currency")
    if home is None or row["currency"] == home:
        return None
    return f"currency {row['currency']} is not the home currency {home}"


def watch_worn(row: Row, context: Context) -> bool:
    """Days the watch wasn't worn, or a fallback device filled in, skip averages.

    A day with no steps recorded, or with few steps and little sedentary time, counts
    as not worn. Both are needed: few steps with no sedentary time recorded counts as
    worn. A day whose ``source`` is one of ``fallback_sources`` (e.g. the phone, on
    days without the watch) counts as not worn too: its row is kept, but it covers
    only part of the day.

    Args:
        row: A parsed activity row with ``steps``, ``sedentary_min`` and ``source``.
        context: Supplies ``watch_off_steps``, ``watch_off_sedentary_min`` and
            ``fallback_sources``.

    Returns:
        True if the day counts toward averages.
    """
    steps, sedentary = row["steps"], row["sedentary_min"]
    if steps is None or row.get("source") in context.options.get(
        "fallback_sources", ()
    ):
        return False
    return (
        steps >= context.options["watch_off_steps"]
        or sedentary is None
        or sedentary >= context.options["watch_off_sedentary_min"]
    )


def inferred_names_input(row: Row, context: Context) -> str | None:
    """An inferred `source` names its input, e.g. `inferred-reflections`.

    Args:
        row: A parsed row.
        context: Unused; part of the check signature.

    Returns:
        An error when an inferred source doesn't name its input, else None.
    """
    source = row.get("source")
    if not isinstance(source, str) or inferred_from(source) != "":
        return None
    return f"source {source!r} must name its input, e.g. inferred-reflections"
