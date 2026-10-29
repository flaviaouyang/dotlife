from datetime import date, time, timedelta
from enum import StrEnum

MINUTES_PER_DAY = 24 * 60
EVENING_START_MINUTES = 18 * 60


class Period(StrEnum):
    """A span to summarise over: Monday-to-Sunday weeks or calendar months."""

    WEEK = "week"
    MONTH = "month"


def period_start(day: date, period: Period) -> date:
    """Return the first day of the period containing a day.

    Args:
        day: Any local date.
        period: Week (starting Monday) or month.

    Returns:
        The Monday of the day's week, or the first of its month.
    """
    if period is Period.WEEK:
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def period_end(start: date, period: Period) -> date:
    """Return the day after a period ends, so periods are half-open: [start, end).

    Args:
        start: First day of the period, as returned by `period_start`.
        period: Week or month.

    Returns:
        The first day of the next period.

    Example:
        >>> period_end(date(2028, 2, 1), Period.MONTH)
        datetime.date(2028, 3, 1)
    """
    if period is Period.WEEK:
        return start + timedelta(days=7)
    return (start.replace(day=28) + timedelta(days=4)).replace(day=1)


def minutes_after_evening(clock: time) -> int:
    """Convert a clock time to minutes after 18:00, so past-midnight times sort last.

    Averaging bedtimes as plain clock times fails across midnight: the mean of 23:30
    and 00:30 is not 12:00. On this scale they are 330 and 390, with a mean of 360,
    which is 00:00.

    Args:
        clock: A local clock time.

    Returns:
        Minutes from 18:00 up to the clock time, from 0 to 1439.

    Example:
        >>> minutes_after_evening(time(0, 30))
        390
    """
    return (clock.hour * 60 + clock.minute - EVENING_START_MINUTES) % MINUTES_PER_DAY


def clock_from_minutes(minutes: float) -> time:
    """Convert minutes after 18:00 back to a clock time, rounded to the minute.

    Args:
        minutes: Minutes after 18:00, e.g. a mean of `minutes_after_evening` values.

    Returns:
        The clock time.

    Example:
        >>> clock_from_minutes(360)
        datetime.time(0, 0)
    """
    total = (EVENING_START_MINUTES + round(minutes)) % MINUTES_PER_DAY
    return time(total // 60, total % 60)
