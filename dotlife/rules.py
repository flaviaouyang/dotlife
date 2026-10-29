from datetime import date, datetime
from typing import cast

from dotlife.schema import Context, Row


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
    """Days the watch wasn't worn (few steps, little sedentary time) skip averages.

    A day with no steps recorded, or with few steps and little sedentary time, counts
    as not worn. Missing sedentary time counts as none.

    Args:
        row: A parsed activity row with ``steps`` and ``sedentary_min``.
        context: Supplies ``watch_off_steps`` and ``watch_off_sedentary_min``.

    Returns:
        True if the day counts toward averages.
    """
    steps = row["steps"]
    if steps is None:
        return False
    return (
        steps >= context.options["watch_off_steps"]
        or (row["sedentary_min"] or 0) >= context.options["watch_off_sedentary_min"]
    )
