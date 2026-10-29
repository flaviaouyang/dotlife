from dotlife.rules import (
    currency_is_home,
    date_is_start_date,
    date_is_wake_date,
    end_after_start,
    watch_worn,
)
from dotlife.schema import (
    DATE,
    END,
    SOURCE,
    START,
    Aggregate,
    Category,
    Field,
    Grain,
    Kind,
    Metric,
)

MINUTES_PER_DAY = 1_440
HOURS_PER_DAY = 24
SUM, MEAN, LAST, DAYS = Aggregate.SUM, Aggregate.MEAN, Aggregate.LAST, Aggregate.DAYS


def text(name: str, required: bool = True) -> Field:
    """Build a text column.

    Args:
        name: Column name.
        required: Whether every row needs a value.

    Returns:
        The field.
    """
    return Field(name, Kind.TEXT, required)


def measured(
    column: str,
    label: str,
    unit: str,
    plausible: tuple[float, float] | None,
    aggregate: Aggregate = MEAN,
    higher_is_better: bool | None = None,
    minimum: float | None = 0,
    related: tuple[str, ...] = (),
) -> Metric:
    """Build a measurement with no hard upper limit, non-negative unless told otherwise.

    Args:
        column: Column name, ending in its unit.
        label: Name shown in the dashboard.
        unit: Unit shown in the dashboard.
        plausible: Bounds for warnings, or None.
        aggregate: How daily values sum up over a period.
        higher_is_better: Which direction is good, if either.
        minimum: Hard lower limit, or None for values that can be negative.
        related: Metrics that usually move with this one, as ``category.column``.

    Returns:
        The metric.
    """
    return Metric(
        column,
        label,
        unit,
        aggregate,
        higher_is_better,
        minimum=minimum,
        plausible=plausible,
        related=related,
    )


def bounded(
    column: str,
    label: str,
    unit: str,
    limits: tuple[float, float],
    aggregate: Aggregate = MEAN,
    higher_is_better: bool | None = None,
    plausible: tuple[float, float] | None = None,
) -> Metric:
    """Build a metric with hard limits on both ends, like a scale or a share of a day.

    Args:
        column: Column name.
        label: Name shown in the dashboard.
        unit: Unit shown in the dashboard.
        limits: The lowest and highest possible values.
        aggregate: How daily values sum up over a period.
        higher_is_better: Which direction is good, if either.
        plausible: Narrower bounds for warnings, or None.

    Returns:
        The metric.
    """
    low, high = limits
    return Metric(
        column, label, unit, aggregate, higher_is_better, low, high, plausible
    )


def minutes(column: str, label: str, higher_is_better: bool | None = None) -> Metric:
    """Build a metric for minutes per day, summed over a period.

    Args:
        column: Column name, ending in ``_min``.
        label: Name shown in the dashboard.
        higher_is_better: Which direction is good, if either.

    Returns:
        The metric, limited to the minutes in a day.
    """
    return bounded(column, label, "min", (0, MINUTES_PER_DAY), SUM, higher_is_better)


def hours(column: str, label: str, higher_is_better: bool | None = None) -> Metric:
    """Build a metric for hours per day, summed over a period.

    Args:
        column: Column name, ending in ``_h``.
        label: Name shown in the dashboard.
        higher_is_better: Which direction is good, if either.

    Returns:
        The metric, limited to the hours in a day.
    """
    return bounded(column, label, "h", (0, HOURS_PER_DAY), SUM, higher_is_better)


def percent(
    column: str, label: str, plausible: tuple[float, float] | None = None
) -> Metric:
    """Build a percentage, averaged over a period.

    Args:
        column: Column name, ending in ``_pct``.
        label: Name shown in the dashboard.
        plausible: Narrower bounds for warnings, or None.

    Returns:
        The metric, limited to 0-100.
    """
    return bounded(column, label, "%", (0, 100), plausible=plausible)


def daily(
    name: str,
    label: str,
    metrics: tuple[Metric, ...],
    item: Field | None = None,
    sensitive: bool = False,
    expect_every_day: bool = False,
) -> Category:
    """Build a category with one row per day, or per day and item.

    Args:
        name: Identifier and config section.
        label: Name shown in the dashboard.
        metrics: Its numeric columns.
        item: A text column that, with the date, identifies a row (e.g. a habit).
        sensitive: Whether it is hidden until "Show sensitive" is on.
        expect_every_day: Whether a day without a row is a gap worth reporting.

    Returns:
        The category, stored in ``<name>.csv``.
    """
    items = () if item is None else (item,)
    return Category(
        name=name,
        label=label,
        file=f"{name}.csv",
        grain=Grain.DAY,
        fields=(DATE, *items, SOURCE),
        metrics=metrics,
        key=("date", *(field.name for field in items)),
        sensitive=sensitive,
        expect_every_day=expect_every_day,
    )


ACTIVITY = Category(
    name="activity",
    label="Activity",
    file="activity.csv",
    grain=Grain.DAY,
    fields=(DATE, SOURCE),
    metrics=(
        measured("steps", "Steps", "steps", (0, 60_000), higher_is_better=True),
        minutes("active_min", "Active time", True),
        bounded(
            "sedentary_min", "Sedentary time", "min", (0, MINUTES_PER_DAY), MEAN, False
        ),
        measured("energy_kcal", "Energy burned", "kcal", (0, 8_000)),
        measured("distance_m", "Distance", "m", (0, 100_000), SUM, True),
        measured("floors", "Floors", "floors", (0, 500), MEAN, True),
    ),
    expect_every_day=True,
    day_filter=watch_worn,
)

WORKOUTS = Category(
    name="workouts",
    label="Workouts",
    file="workouts.csv",
    grain=Grain.SESSION,
    fields=(DATE, START, END, text("type"), SOURCE),
    metrics=(
        measured("avg_hr_bpm", "Average heart rate", "bpm", (40, 220)),
        measured("distance_m", "Distance", "m", (0, 300_000), SUM, True),
        measured("energy_kcal", "Energy burned", "kcal", (0, 5_000), SUM),
    ),
    key=("start",),
    checks=(end_after_start, date_is_start_date),
)

SLEEP = Category(
    name="sleep",
    label="Sleep",
    file="sleep.csv",
    grain=Grain.SESSION,
    fields=(DATE, START, END, SOURCE),
    metrics=tuple(
        bounded(column, label, "min", (0, MINUTES_PER_DAY), MEAN, better)
        for column, label, better in (
            ("asleep_min", "Time asleep", True),
            ("deep_min", "Deep sleep", True),
            ("rem_min", "REM sleep", True),
            ("light_min", "Light sleep", None),
            ("awake_min", "Time awake", False),
        )
    ),
    key=("start",),
    expect_every_day=True,
    checks=(end_after_start, date_is_wake_date),
)

HEART = daily(
    "heart",
    "Heart",
    (
        measured("resting_hr_bpm", "Resting heart rate", "bpm", (30, 120), MEAN, False),
        measured("hrv_ms", "Heart rate variability", "ms", (5, 250), MEAN, True),
    ),
    expect_every_day=True,
)

BODY = daily(
    "body",
    "Body",
    (
        measured("weight_kg", "Weight", "kg", (25, 300)),
        percent("body_fat_pct", "Body fat", (3, 60)),
        measured("waist_cm", "Waist", "cm", (40, 200)),
    ),
)

FITNESS_MARKERS = daily(
    "fitness_markers",
    "Fitness markers",
    (
        measured(
            "vo2max_ml_kg_min",
            "VO2 max",
            "ml/kg/min",
            (10, 90),
            LAST,
            True,
            related=("heart.resting_hr_bpm", "activity.active_min"),
        ),
    ),
)

VITALS = daily(
    "vitals",
    "Vitals",
    (
        measured("systolic_mmhg", "Systolic blood pressure", "mmHg", (70, 220)),
        measured("diastolic_mmhg", "Diastolic blood pressure", "mmHg", (40, 140)),
        percent("spo2_pct", "Blood oxygen", (80, 100)),
        measured("respiratory_rate_brpm", "Respiratory rate", "breaths/min", (6, 40)),
        measured(
            "skin_temp_delta_c", "Skin temperature change", "°C", (-3, 3), minimum=None
        ),
    ),
)

NUTRITION = daily(
    "nutrition",
    "Nutrition",
    (
        measured("energy_in_kcal", "Energy eaten", "kcal", (0, 8_000)),
        measured("protein_g", "Protein", "g", (0, 1_000)),
        measured("carbs_g", "Carbohydrates", "g", (0, 1_000)),
        measured("fat_g", "Fat", "g", (0, 1_000)),
        measured("water_ml", "Water", "ml", (0, 10_000), MEAN, True),
        measured("caffeine_mg", "Caffeine", "mg", (0, 1_500), MEAN, False),
        measured("alcohol_drinks", "Alcohol", "drinks", (0, 30), SUM, False),
    ),
)

MINDFULNESS = daily(
    "mindfulness", "Mindfulness", (minutes("mindful_min", "Mindful time", True),)
)

CYCLE = daily(
    "cycle",
    "Menstrual cycle",
    (
        bounded("flow_level", "Flow", "0-3", (0, 3), DAYS),
        measured("bbt_c", "Basal body temperature", "°C", (35, 38)),
    ),
    sensitive=True,
)

MEDICATION = daily(
    "medication",
    "Medication",
    (measured("doses", "Doses", "doses", (0, 20), SUM),),
    item=text("item"),
    sensitive=True,
)

SYMPTOMS = daily(
    "symptoms",
    "Symptoms",
    (bounded("severity", "Severity", "0-10", (0, 10), MEAN, False),),
    item=text("symptom"),
    sensitive=True,
)

GLUCOSE = daily(
    "glucose",
    "Blood glucose",
    (
        measured("glucose_mean_mmol_l", "Mean glucose", "mmol/L", (2, 25)),
        percent("time_in_range_pct", "Time in range"),
    ),
    sensitive=True,
)

MOOD = daily(
    "mood",
    "Mood",
    (
        bounded("mood", "Mood", "1-5", (1, 5), MEAN, True),
        bounded("energy", "Energy", "1-5", (1, 5), MEAN, True),
        bounded("stress", "Stress", "1-5", (1, 5), MEAN, False),
    ),
)

JOURNAL = Category(
    name="journal",
    label="Journal",
    file="journal/",
    grain=Grain.ENTRY,
    fields=(DATE, text("text")),
    metrics=(),
    sensitive=True,
)

TIME = daily("time", "Time use", (hours("hours", "Hours"),), item=text("category"))

SCREEN_TIME = daily(
    "screen_time",
    "Screen time",
    (
        bounded("screen_min", "Screen time", "min", (0, MINUTES_PER_DAY), MEAN, False),
        measured("pickups", "Pickups", "pickups", (0, 1_000), MEAN, False),
    ),
    expect_every_day=True,
)

TASKS = daily(
    "tasks",
    "Tasks",
    (measured("tasks_done", "Tasks done", "tasks", (0, 200), SUM, True),),
)

HABITS = daily(
    "habits",
    "Habits",
    (measured("times", "Days done", "times", (0, 100), DAYS, True),),
    item=text("habit"),
)

READING = daily(
    "reading",
    "Reading",
    (
        measured("pages", "Pages", "pages", (0, 2_000), SUM, True),
        minutes("reading_min", "Reading time", True),
        measured("books_finished", "Books finished", "books", (0, 20), SUM, True),
    ),
)

LEARNING = daily(
    "learning",
    "Learning",
    (
        minutes("learning_min", "Learning time", True),
        measured("lessons", "Lessons", "lessons", (0, 100), SUM, True),
    ),
    item=text("subject"),
)

MEDIA = daily(
    "media",
    "Media",
    (
        minutes("listening_min", "Listening time"),
        measured("episodes", "Episodes", "episodes", (0, 50), SUM),
        measured("films", "Films", "films", (0, 20), SUM),
    ),
)

FINANCES = Category(
    name="finances",
    label="Finances",
    file="finances.csv",
    grain=Grain.TRANSACTION,
    fields=(
        DATE,
        text("category"),
        text("account", required=False),
        text("currency"),
        text("description", required=False),
        SOURCE,
    ),
    metrics=(Metric("amount", "Amount", "", SUM),),
    key=(),
    sensitive=True,
    warnings=(currency_is_home,),
)

EVENTS = Category(
    name="events",
    label="Life events",
    file="events.csv",
    grain=Grain.EVENT,
    fields=(DATE, text("label")),
    metrics=(),
    key=(),
)

WEATHER = daily(
    "weather",
    "Weather",
    (
        measured("temp_mean_c", "Mean temperature", "°C", (-50, 50), minimum=None),
        hours("daylight_h", "Daylight"),
        measured("precipitation_mm", "Precipitation", "mm", (0, 500), SUM),
    ),
    expect_every_day=True,
)

SOCIAL = daily(
    "social", "Social", (hours("social_h", "Time with people"),), sensitive=True
)

TRAVEL = Category(
    name="travel",
    label="Travel",
    file="travel.csv",
    grain=Grain.DAY,
    fields=(DATE, text("country", required=False), SOURCE),
    metrics=(bounded("travel_day", "Travel days", "days", (0, 1), DAYS),),
    sensitive=True,
)

CATEGORIES = (
    ACTIVITY,
    WORKOUTS,
    SLEEP,
    HEART,
    BODY,
    FITNESS_MARKERS,
    VITALS,
    NUTRITION,
    MINDFULNESS,
    CYCLE,
    MEDICATION,
    SYMPTOMS,
    GLUCOSE,
    MOOD,
    JOURNAL,
    TIME,
    SCREEN_TIME,
    TASKS,
    HABITS,
    READING,
    LEARNING,
    MEDIA,
    FINANCES,
    EVENTS,
    WEATHER,
    SOCIAL,
    TRAVEL,
)
