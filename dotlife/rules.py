from datetime import datetime
from typing import cast

from dotlife.schema import Context, Row


def end_after_start(row: Row, context: Context) -> str | None:
    """Check that a session ends after it starts.

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
    """Check that a sleep session is filed under the local date its sleeper woke up.

    Args:
        row: A parsed row with ``date`` and an ``end`` timestamp.
        context: Supplies the user's time zone, which handles DST and sessions
            recorded with another UTC offset.

    Returns:
        A problem description, or None when the row is fine.
    """
    wake_date = cast(datetime, row["end"]).astimezone(context.timezone).date()
    if row["date"] == wake_date:
        return None
    return (
        f"date {row['date']} should be the wake date {wake_date}: "
        "a night counts toward the day you woke up"
    )


def watch_worn(row: Row, context: Context) -> bool:
    """Decide whether a watch was worn on a day, so watch-off days stay out of averages.

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
