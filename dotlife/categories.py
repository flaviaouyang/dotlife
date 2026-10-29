from dotlife.rules import date_is_wake_date, end_after_start, watch_worn
from dotlife.schema import (
    DATE,
    END,
    SOURCE,
    START,
    Aggregate,
    Category,
    Grain,
    Metric,
)

ACTIVITY = Category(
    name="activity",
    label="Activity",
    file="activity.csv",
    grain=Grain.DAY,
    fields=(DATE, SOURCE),
    metrics=(
        Metric("steps", "Steps", "steps", 0, 100_000, Aggregate.MEAN, True),
        Metric("active_min", "Active time", "min", 0, 1_440, Aggregate.SUM, True),
        Metric(
            "sedentary_min", "Sedentary time", "min", 0, 1_440, Aggregate.MEAN, False
        ),
        Metric("energy_kcal", "Energy burned", "kcal", 0, 10_000, Aggregate.MEAN),
        Metric("distance_m", "Distance", "m", 0, 200_000, Aggregate.SUM, True),
        Metric("floors", "Floors climbed", "floors", 0, 1_000, Aggregate.MEAN, True),
    ),
    day_filter=watch_worn,
)

SLEEP = Category(
    name="sleep",
    label="Sleep",
    file="sleep.csv",
    grain=Grain.SESSION,
    fields=(DATE, START, END, SOURCE),
    metrics=(
        Metric("asleep_min", "Time asleep", "min", 0, 1_440, Aggregate.MEAN, True),
    ),
    key=("start",),
    checks=(end_after_start, date_is_wake_date),
)

MOOD = Category(
    name="mood",
    label="Mood",
    file="mood.csv",
    grain=Grain.DAY,
    fields=(DATE, SOURCE),
    metrics=(
        Metric("mood", "Mood", "1-5", 1, 5, Aggregate.MEAN, True),
        Metric("energy", "Energy", "1-5", 1, 5, Aggregate.MEAN, True),
        Metric("stress", "Stress", "1-5", 1, 5, Aggregate.MEAN, False),
    ),
)

CATEGORIES = (ACTIVITY, SLEEP, MOOD)
