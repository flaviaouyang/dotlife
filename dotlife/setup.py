import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import tomlkit

from dotlife.categories import AREA_OF, AREAS, CATEGORIES
from dotlife.terminal import Option, Prompter

MANUAL = "manual"
FROM_REFLECTIONS = "inferred-reflections"
FROM_FINANCES = "inferred-finances"
DINING_OUT = "dining_out"
DINING_OUT_METRIC = {
    "label": "Dining out",
    "unit": "times",
    "summary": "sum",
    "minimum": 0,
    "plausible": [0, 10],
}
INFERABLE_FROM_REFLECTIONS = ("mood", "social", "habits")
CURRENCY = re.compile(r"[A-Z]{3}")
PERIODS = ("week", "month")
WEIGHTS = ("kg", "lb")
GLUCOSE_UNITS = ("mmol/L", "mg/dL")
SOURCE_VALUE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
ANSWER_KEYS = (
    "timezone",
    "period",
    "weight",
    "glucose",
    "track",
    "sources",
    "home_currency",
    "budgets",
    "location",
)
CUSTOM_AREA = AREAS[-1]
DIMENSIONS = {
    "Body and health": "Movement, sleep, heart, body measurements and health records.",
    "Mind": "How you feel and what you think: mood ratings and written reflections.",
    "Time and work": "Where your hours go: calendar time, screens and tasks.",
    "Habits and leisure": "Things you do on purpose: habits, reading, learning, media.",
    "Money": "Spending, against monthly budgets if you set them.",
    "Context": "What surrounds the numbers: life events, weather, people, travel.",
    CUSTOM_AREA: "Numbers you defined yourself in config.toml.",
}
CATEGORY_HINTS = {
    "activity": "Steps, active time, energy, distance, floors",
    "workouts": "Each session: type, duration, heart rate, distance",
    "sleep": "Each night: time asleep and sleep stages",
    "heart": "Resting heart rate and heart rate variability",
    "body": "Weight, body fat, waist, height",
    "fitness_markers": "VO2 max",
    "vitals": "Blood pressure, blood oxygen, breathing rate, skin temperature",
    "nutrition": "Calories, protein, carbs, fat, water, caffeine, alcohol",
    "mindfulness": "Minutes of meditation or breathing exercises",
    "cycle": "Period days, flow and basal body temperature",
    "medication": "Doses taken, per medication",
    "symptoms": "How strong each symptom was, 0 to 10",
    "glucose": "Mean glucose and time in range",
    "mood": "Mood, energy and stress, 1 to 5",
    "reflections": "Short notes through the day, in jrnl's plain-text format",
    "time": "Hours per category each day, e.g. from your calendar",
    "screen_time": "Minutes on screens and phone pickups",
    "tasks": "Tasks done each day",
    "habits": "Which habits you did each day",
    "reading": "Pages, minutes and books finished",
    "learning": "Minutes and lessons, per subject",
    "media": "Listening minutes, episodes and films",
    "finances": "Transactions, with budgets and spending by category",
    "events": "Life events that label your charts, e.g. a new job",
    "weather": "Temperature, daylight and rain where you live",
    "social": "Hours spent with other people",
    "travel": "Days away from home, and where",
}
SOURCES_START = "<!-- dotlife setup:start (written by `dotlife setup`) -->"
SOURCES_END = "<!-- dotlife setup:end -->"
SOURCES_INTRO = """# Sources

Where each kind of data comes from, which source wins when two report the same
thing, and the choices each source's guide leaves to you. `dotlife setup` writes
the part between the markers; the `setup` and `maintain` skills add the rest.
"""


@dataclass(frozen=True, slots=True)
class Guide:
    """A source with a guide in ``docs/sources/``.

    Attributes:
        slug: Its name in ``[sources]``.
        label: Its name for people.
        categories: The categories its guide fills.
        guide: The guide's file name in ``docs/sources/``.
        automatic: Whether it needs no account, so setup assumes it for its
            categories when nothing else covers them.
    """

    slug: str
    label: str
    categories: tuple[str, ...]
    guide: str = ""
    automatic: bool = False

    @property
    def file(self) -> str:
        """The guide's file name."""
        return self.guide or f"{self.slug}.md"


CALENDAR = ("time", "events", "social", "travel")
GUIDES = (
    Guide(
        "apple-health",
        "Apple Health",
        (
            "activity",
            "workouts",
            "sleep",
            "heart",
            "body",
            "fitness_markers",
            "vitals",
            "nutrition",
            "mindfulness",
            "cycle",
            "medication",
            "symptoms",
            "glucose",
            "mood",
        ),
    ),
    Guide(
        "google-health",
        "Google Health (formerly Fitbit)",
        (
            "activity",
            "workouts",
            "sleep",
            "heart",
            "body",
            "fitness_markers",
            "vitals",
            "nutrition",
            "glucose",
        ),
    ),
    Guide(
        "oura",
        "Oura",
        (
            "activity",
            "workouts",
            "sleep",
            "heart",
            "vitals",
            "fitness_markers",
            "mindfulness",
        ),
    ),
    Guide(
        "whoop", "WHOOP", ("activity", "workouts", "sleep", "heart", "body", "vitals")
    ),
    Guide("jrnl", "jrnl", ("reflections",)),
    Guide(
        "obsidian-daily-notes",
        "Obsidian daily notes",
        ("mood", "habits", "tasks", "reflections"),
    ),
    Guide("apple-calendar", "Apple Calendar", CALENDAR),
    Guide("google-calendar", "Google Calendar", CALENDAR),
    Guide("outlook-calendar", "Outlook calendar", CALENDAR),
    Guide("open-meteo", "Open-Meteo", ("weather",), "weather.md", automatic=True),
)
GUIDE_BY_SLUG = {guide.slug: guide for guide in GUIDES}
SOURCE_LABELS = {
    **{guide.slug: guide.label for guide in GUIDES},
    FROM_REFLECTIONS: "Inferred from reflections (AI)",
    FROM_FINANCES: "Inferred from transactions (rule)",
    MANUAL: "By hand",
}


@dataclass(frozen=True, slots=True)
class Answers:
    """Everything ``dotlife setup`` asks.

    Attributes:
        timezone: IANA time zone name.
        period: ``week`` or ``month``.
        weight: ``kg`` or ``lb``.
        glucose: ``mmol/L`` or ``mg/dL``.
        track: Categories to track, built-in and custom.
        sources: Per category, its sources, best first.
        home_currency: ISO 4217 code, for finances.
        budgets: Monthly budget per spending category, in the home currency.
        location: Home latitude and longitude for weather, rounded to two
            decimals, or None.
    """

    timezone: str
    period: str = "week"
    weight: str = "kg"
    glucose: str = "mmol/L"
    track: tuple[str, ...] = ()
    sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    home_currency: str = "EUR"
    budgets: Mapping[str, float] = field(default_factory=dict)
    location: tuple[float, float] | None = None


def local_timezone() -> str | None:
    """Find this computer's time zone name from ``/etc/localtime``.

    Returns:
        The IANA name, e.g. ``Europe/London``, or None where it can't be read.
    """
    try:
        target = Path("/etc/localtime").resolve(strict=True)
    except OSError:
        return None
    parts = target.parts
    if "zoneinfo" not in parts:
        return None
    return "/".join(parts[parts.index("zoneinfo") + 1 :]) or None


def timezone_problem(name: str) -> str | None:
    """Check a time zone name.

    Args:
        name: What was typed.

    Returns:
        Why it's wrong, or None.
    """
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return f"{name!r} isn't an IANA time zone name, e.g. Europe/London."
    return None


def current_answers(config: Mapping[str, Any]) -> Answers:
    """Read the answers already in config.toml, to offer them as defaults.

    Before the first setup (no ``track``), the time zone is this computer's.

    Args:
        config: The whole of config.toml.

    Returns:
        The answers config.toml implies.
    """
    set_up = "track" in config
    finances = config.get("finances", {})
    return Answers(
        timezone=(config.get("timezone") if set_up else None)
        or local_timezone()
        or config.get("timezone", "UTC"),
        period=config.get("dashboard", {}).get("period", "week"),
        weight=config.get("display", {}).get("weight", "kg"),
        glucose=config.get("display", {}).get("glucose", "mmol/L"),
        track=tuple(config.get("track", ())),
        sources={
            name: tuple(values) for name, values in config.get("sources", {}).items()
        },
        home_currency=finances.get("home_currency", "EUR"),
        budgets=dict(finances.get("budgets", {})),
        location=(weather["latitude"], weather["longitude"])
        if {"latitude", "longitude"} <= set(weather := config.get("weather", {}))
        else None,
    )


def slug(name: str) -> str:
    """Turn a source's name into a lowercase, hyphenated value.

    Args:
        name: The name, e.g. "Bank of Example".

    Returns:
        E.g. ``bank-of-example``.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_budgets(text: str) -> dict[str, float]:
    """Read budgets typed as ``category=amount`` pairs.

    Args:
        text: E.g. ``groceries=400, eating_out=150``; ``none`` for no budgets.

    Returns:
        Amount by category.

    Raises:
        ValueError: If a pair isn't ``name=number``.

    Example:
        >>> parse_budgets("groceries=400, eating_out=150")
        {'groceries': 400.0, 'eating_out': 150.0}
    """
    if text.strip().lower() == "none":
        return {}
    pairs = [part.split("=") for part in text.split(",") if part.strip()]
    if any(len(pair) != 2 or not pair[0].strip() for pair in pairs):
        raise ValueError(text)
    return {name.strip(): float(amount) for name, amount in pairs}


def parse_location(text: str) -> tuple[float, float]:
    """Read a location typed as ``latitude, longitude``, rounded to two decimals.

    Args:
        text: E.g. ``51.5072, -0.1276``.

    Returns:
        Latitude and longitude, each to two decimals (about a kilometre).

    Raises:
        ValueError: If it isn't two numbers within range.

    Example:
        >>> parse_location("51.5072, -0.1276")
        (51.51, -0.13)
    """
    latitude, longitude = (float(part) for part in text.split(","))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError(text)
    return round(latitude, 2), round(longitude, 2)


def location_problem(text: str) -> str | None:
    """Check a location typed as ``latitude, longitude``.

    Args:
        text: What was typed.

    Returns:
        Why it's wrong, or None.
    """
    try:
        parse_location(text)
    except ValueError:
        return "Write latitude, longitude, e.g. 51.51, -0.13."
    return None


def budget_problem(text: str) -> str | None:
    """Check budgets typed as ``category=amount`` pairs.

    Args:
        text: What was typed.

    Returns:
        Why it's wrong, or None.
    """
    try:
        parse_budgets(text)
    except ValueError:
        return "Write category=amount pairs, e.g. groceries=400, eating_out=150."
    return None


def budgets_text(budgets: Mapping[str, float]) -> str:
    """Show budgets the way they're typed.

    Args:
        budgets: Amount by category.

    Returns:
        E.g. ``groceries=400, eating_out=150``, or ``none``.
    """
    return ", ".join(f"{name}={amount:g}" for name, amount in budgets.items()) or "none"


def category_labels(custom: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """Name every category for people, custom metrics included.

    Args:
        custom: The ``[custom]`` tables in config.toml.

    Returns:
        Label by category name.
    """
    return (
        {category.name: category.label for category in CATEGORIES}
        | {DINING_OUT: str(DINING_OUT_METRIC["label"])}
        | {name: spec.get("label", name) for name, spec in custom.items()}
    )


def dimension_of(name: str) -> str:
    """Return a category's dimension; custom metrics have their own.

    Args:
        name: A category name.

    Returns:
        The dimension, e.g. "Body and health".
    """
    return AREA_OF.get(name, CUSTOM_AREA)


def source_label(value: str) -> str:
    """Name a source for people.

    Args:
        value: Its value in ``[sources]``.

    Returns:
        Its label, or the value itself for a source without a guide.
    """
    return SOURCE_LABELS.get(value, value)


def ask_basics(prompter: Prompter, current: Answers) -> tuple[str, str]:
    """Ask for the time zone and the period summaries use.

    Args:
        prompter: Asks the questions.
        current: The answers so far, for defaults.

    Returns:
        The time zone and the period.
    """
    prompter.heading("The basics", "Dates and weeks follow your time zone.")
    timezone = prompter.text(
        "timezone", "Your time zone", current.timezone, timezone_problem
    )
    period = prompter.select(
        "period",
        "Summarise by",
        [
            Option("week", "Week", "Monday to Sunday"),
            Option("month", "Month", "Calendar months"),
        ],
        current.period,
    )
    return timezone, period


def ask_categories(
    prompter: Prompter,
    current: Answers,
    names: Sequence[str],
    labels: Mapping[str, str],
) -> list[str]:
    """Ask which dimensions to track, then which categories in each.

    Args:
        prompter: Asks the questions.
        current: The answers so far, for defaults.
        names: Every category name, built-in then custom.
        labels: Label by category name.

    Returns:
        The categories to track, in the order shown.
    """
    prompter.heading(
        "What to track",
        "Pick the parts of life you want on your dashboard, then the details in "
        "each. Everything you don't pick stays off.",
    )
    by_dimension = {
        dimension: [name for name in names if dimension_of(name) == dimension]
        for dimension in AREAS
    }
    dimensions = [dimension for dimension, members in by_dimension.items() if members]
    picked = prompter.checkbox(
        "dimensions",
        "Which parts of life?",
        [
            Option(
                dimension,
                dimension,
                f"{DIMENSIONS[dimension]} E.g. "
                + ", ".join(labels[name] for name in by_dimension[dimension][:4])
                + ".",
            )
            for dimension in dimensions
        ],
        [
            dimension
            for dimension in dimensions
            if any(name in current.track for name in by_dimension[dimension])
        ],
    )
    sensitive = {category.name for category in CATEGORIES if category.sensitive}
    track: list[str] = []
    for dimension in picked:
        members = by_dimension[dimension]
        track += prompter.checkbox(
            f"categories:{dimension}",
            f"{dimension}: which of these?",
            [
                Option(
                    name,
                    labels[name] + (" (sensitive)" if name in sensitive else ""),
                    CATEGORY_HINTS.get(name, ""),
                )
                for name in members
            ],
            [name for name in members if name in current.track]
            or (
                []
                if current.track
                else [name for name in members if name not in sensitive]
            ),
        )
    chosen = [name for name in track if name in sensitive]
    if chosen:
        prompter.note(
            "Sensitive categories stay hidden in the dashboard until you switch on "
            "Show sensitive, so they don't appear when you share your screen."
        )
        kept = prompter.checkbox(
            "sensitive",
            "You picked these sensitive categories. Untick any to leave out.",
            [Option(name, labels[name]) for name in chosen],
            chosen,
        )
        track = [name for name in track if name not in sensitive or name in kept]
    return track


def ask_details(
    prompter: Prompter, current: Answers, track: Sequence[str]
) -> tuple[str, str, str, dict[str, float], bool, tuple[float, float] | None]:
    """Ask the questions only some categories need: units, money, location.

    Args:
        prompter: Asks the questions.
        current: The answers so far, for defaults.
        track: The categories to track.

    Returns:
        Weight unit, glucose unit, home currency, budgets, whether to count
        dining out, and the home location for weather.
    """
    weight, glucose = current.weight, current.glucose
    currency, budgets = current.home_currency, dict(current.budgets)
    dining, location = False, current.location
    needs = {"body", "glucose", "finances", "weather"} & set(track)
    if not needs:
        return weight, glucose, currency, budgets, dining, location
    prompter.heading("A few details")
    if "body" in track:
        weight = prompter.select(
            "weight",
            "Show weight in",
            [Option("kg", "Kilograms"), Option("lb", "Pounds")],
            current.weight,
        )
    if "glucose" in track:
        glucose = prompter.select(
            "glucose",
            "Show blood glucose in",
            [Option("mmol/L", "mmol/L"), Option("mg/dL", "mg/dL")],
            current.glucose,
        )
    if "finances" in track:
        currency = prompter.text(
            "currency",
            "Your home currency (ISO 4217 code)",
            current.home_currency,
            lambda code: None if CURRENCY.fullmatch(code) else "Use a code like EUR.",
        )
        budgets = parse_budgets(
            prompter.text(
                "budgets",
                "Monthly budgets, as category=amount pairs, or none",
                budgets_text(current.budgets),
                budget_problem,
            )
        )
        dining = prompter.confirm(
            "dining_out",
            "Count how often you dine out from your transactions? (A rule, no AI.)",
            DINING_OUT in current.track,
        )
    if "weather" in track:
        prompter.note(
            "Weather needs your home location. Two decimals is about a kilometre: "
            "close enough for weather, without your address in config.toml."
        )
        location = parse_location(
            prompter.text(
                "location",
                "Home location as latitude, longitude",
                "" if current.location is None else "{}, {}".format(*current.location),
                location_problem,
            )
        )
    return weight, glucose, currency, budgets, dining, location


def ask_source_pool(
    prompter: Prompter,
    current: Answers,
    track: Sequence[str],
    labels: Mapping[str, str],
) -> list[str]:
    """Ask which apps and devices the person uses, best first where they overlap.

    Args:
        prompter: Asks the questions.
        current: The answers so far, for defaults.
        track: The categories to track.
        labels: Label by category name.

    Returns:
        Their sources, ranked: guides first in the person's order, then others.
    """
    prompter.heading(
        "Where your data comes from",
        "Tick the apps and devices you use. We'll work out what each one fills, "
        "and you can check it afterwards.",
    )
    previous = list(
        dict.fromkeys(value for values in current.sources.values() for value in values)
    )
    relevant = [
        guide
        for guide in GUIDES
        if set(guide.categories) & set(track) and not guide.automatic
    ]
    picked = prompter.checkbox(
        "sources",
        "Which of these do you use?",
        [
            Option(
                guide.slug,
                guide.label,
                "Fills "
                + ", ".join(labels[name] for name in guide.categories if name in track)
                + ".",
            )
            for guide in relevant
        ],
        [guide.slug for guide in relevant if guide.slug in previous],
    )
    known = {*GUIDE_BY_SLUG, FROM_REFLECTIONS, FROM_FINANCES, MANUAL}
    others = prompter.text(
        "other_sources",
        "Anything else, e.g. a bank or another app? Names, separated by commas",
        ", ".join(value for value in previous if value not in known) or "none",
        lambda text: None,
    )
    extra = (
        [] if others.strip() == "none" else [slug(name) for name in others.split(",")]
    )
    pool = list(dict.fromkeys(picked + [value for value in extra if value]))
    pool.sort(
        key=lambda value: previous.index(value) if value in previous else len(previous)
    )
    overlapping = [
        value
        for value in pool
        if value in GUIDE_BY_SLUG
        and any(
            other != value
            and other in GUIDE_BY_SLUG
            and set(GUIDE_BY_SLUG[value].categories)
            & set(GUIDE_BY_SLUG[other].categories)
            & set(track)
            for other in pool
        )
    ]
    if len(overlapping) < 2:
        return pool
    prompter.note(
        "Some of these record the same things. When two report the same day, the "
        "one ranked higher wins."
    )
    ranked = prompter.rank(
        "rank",
        "Rank them, most trusted first",
        [Option(value, source_label(value)) for value in overlapping],
    )
    return ranked + [value for value in pool if value not in ranked]


def assume_sources(
    track: Sequence[str], pool: Sequence[str], current: Answers
) -> dict[str, tuple[str, ...]]:
    """Work out each category's sources from the person's apps and devices.

    A category keeps its previous sources while they are all still in use. Else it
    gets every ranked source whose guide fills it; failing that, a source that
    needs no account (weather); failing that, by hand.

    Args:
        track: The categories to track.
        pool: The person's sources, ranked.
        current: The answers so far.

    Returns:
        Sources by category, best first.
    """
    usable = {*pool, MANUAL, FROM_REFLECTIONS, FROM_FINANCES}
    sources: dict[str, tuple[str, ...]] = {}
    for name in track:
        previous = current.sources.get(name, ())
        if name == DINING_OUT:
            sources[name] = (FROM_FINANCES,)
        elif previous and set(previous) <= usable:
            sources[name] = previous
        else:
            covering = tuple(
                value
                for value in pool
                if value in GUIDE_BY_SLUG and name in GUIDE_BY_SLUG[value].categories
            )
            automatic = tuple(
                guide.slug
                for guide in GUIDES
                if guide.automatic and name in guide.categories
            )
            sources[name] = covering or automatic or (MANUAL,)
    return sources


def source_options(
    name: str, pool: Sequence[str], track: Sequence[str]
) -> list[Option]:
    """List the sources a category can come from, for changing it in the review.

    Args:
        name: The category.
        pool: The person's sources.
        track: The categories to track, which decides what can be inferred.

    Returns:
        The person's sources that fit, other guides that fill it, inference where
        it applies, and by hand.
    """
    fitting = [
        value
        for value in pool
        if value not in GUIDE_BY_SLUG or name in GUIDE_BY_SLUG[value].categories
    ]
    guides = [
        guide.slug
        for guide in GUIDES
        if name in guide.categories and guide.slug not in fitting
    ]
    inferred = (
        [FROM_REFLECTIONS]
        if name in INFERABLE_FROM_REFLECTIONS and "reflections" in track
        else []
    )
    return [
        Option(value, source_label(value))
        for value in [*fitting, *guides, *inferred, MANUAL]
    ]


def review_sources(
    prompter: Prompter,
    sources: dict[str, tuple[str, ...]],
    pool: Sequence[str],
    track: Sequence[str],
    labels: Mapping[str, str],
) -> dict[str, tuple[str, ...]]:
    """Show the assumed sources and let the person change any category.

    Args:
        prompter: Asks the questions.
        sources: The assumed sources by category, best first.
        pool: The person's sources.
        track: The categories to track.
        labels: Label by category name.

    Returns:
        The sources once the person says they look right.
    """
    sources = dict(sources)
    while True:
        prompter.heading(
            "Check our assumptions",
            "Here is where we think each category comes from, best first.",
        )
        width = max(len(labels[name]) for name in sources) if sources else 0
        for name, values in sources.items():
            prompter.say(
                f"  {labels[name]:<{width}}  "
                + " > ".join(source_label(value) for value in values)
            )
        if any(values == (MANUAL,) for values in sources.values()):
            prompter.note(
                "By hand means no source fills it yet: you'd type the values into "
                "its file, or pick a source here."
            )
        changing = prompter.select(
            "review",
            "Does this look right?",
            [Option("ok", "Yes, looks right")]
            + [
                Option(name, f"Change {labels[name]}")
                for name in sources
                if name != DINING_OUT
            ],
            "ok",
        )
        if changing == "ok":
            return sources
        picked = prompter.checkbox(
            f"change:{changing}",
            f"Where does {labels[changing]} come from?",
            source_options(changing, pool, track),
            sources[changing],
        ) or [MANUAL]
        if len(picked) > 1:
            picked = prompter.rank(
                f"order:{changing}",
                f"Rank the sources for {labels[changing]}, most trusted first",
                [Option(value, source_label(value)) for value in picked],
            )
        sources[changing] = tuple(picked)


def ask_answers(
    prompter: Prompter,
    current: Answers,
    custom: Sequence[str],
    labels: Mapping[str, str],
) -> Answers:
    """Ask every question, offering the current answers as defaults.

    Args:
        prompter: Asks the questions.
        current: The answers so far.
        custom: Custom metric names in config.toml, besides dining out.
        labels: Label by category name.

    Returns:
        The new answers.
    """
    timezone, period = ask_basics(prompter, current)
    names = [
        name
        for dimension in AREAS
        for name in [category.name for category in CATEGORIES] + list(custom)
        if dimension_of(name) == dimension
    ]
    track = ask_categories(prompter, current, names, labels)
    weight, glucose, currency, budgets, dining, location = ask_details(
        prompter, current, track
    )
    if dining:
        track.append(DINING_OUT)
    pool = ask_source_pool(prompter, current, track, labels)
    sources = review_sources(
        prompter, assume_sources(track, pool, current), pool, track, labels
    )
    return Answers(
        timezone,
        period,
        weight,
        glucose,
        tuple(track),
        sources,
        currency,
        budgets,
        location,
    )


def summary(answers: Answers, labels: Mapping[str, str]) -> list[str]:
    """Describe the answers for a last look before writing.

    Args:
        answers: The answers.
        labels: Label by category name.

    Returns:
        Lines to show.
    """
    lines = [
        f"Time zone {answers.timezone}, by {answers.period}, "
        f"{answers.weight} and {answers.glucose}.",
        f"Tracking {len(answers.track)} categories from "
        f"{len({value for values in answers.sources.values() for value in values})} "
        "sources.",
    ]
    if "finances" in answers.track:
        lines.append(
            f"Currency {answers.home_currency}; "
            f"budgets {budgets_text(answers.budgets)}."
        )
    return lines


def next_step() -> str:
    """Say what to do after the questionnaire, which is the path without an agent.

    Returns:
        A short paragraph.
    """
    return (
        "Next, set up your sources: start at docs/sources/README.md, open the guide "
        "for each source in sources.md, write its script, and list it under "
        "[[fresh.steps]] in config.toml. Then run make fresh. Tip: an AI coding "
        "agent can do all of this for you with the setup skill (/setup in Claude "
        "Code)."
    )


def answers_json(answers: Answers) -> str:
    """Show answers as the JSON ``dotlife setup --answers`` reads.

    Args:
        answers: The answers.

    Returns:
        Indented JSON.
    """
    return json.dumps(
        {
            "timezone": answers.timezone,
            "period": answers.period,
            "weight": answers.weight,
            "glucose": answers.glucose,
            "track": list(answers.track),
            "sources": {name: list(values) for name, values in answers.sources.items()},
            "home_currency": answers.home_currency,
            "budgets": dict(answers.budgets),
            "location": None if answers.location is None else list(answers.location),
        },
        indent=2,
    )


def one_of(key: str, value: Any, allowed: Sequence[str]) -> str:
    """Check that an answer is one of a few values.

    Args:
        key: The answer's name, for the message.
        value: The answer.
        allowed: The values it may take.

    Returns:
        The answer.

    Raises:
        ValueError: If it isn't one of them.
    """
    if value not in allowed:
        raise ValueError(f"{key} must be one of {', '.join(allowed)}, not {value!r}")
    return value


def answers_from(
    data: Mapping[str, Any], current: Answers, names: Sequence[str]
) -> Answers:
    """Check answers an agent gathered, filling the rest from the current ones.

    Args:
        data: Parsed JSON; any of the keys ``answers_json`` writes.
        current: The answers in config.toml now, for keys left out.
        names: Every category that can be tracked, custom ones included.

    Returns:
        The answers.

    Raises:
        ValueError: With a plain message, at the first answer that's wrong.
    """
    unknown = sorted(set(data) - set(ANSWER_KEYS))
    if unknown:
        raise ValueError(f"unknown answers: {', '.join(unknown)}")
    merged = json.loads(answers_json(current)) | dict(data)
    if (problem := timezone_problem(str(merged["timezone"]))) is not None:
        raise ValueError(problem)
    track = list(merged["track"])
    if strays := [name for name in track if name not in {*names, DINING_OUT}]:
        raise ValueError(f"track lists unknown categories: {', '.join(strays)}")
    sources = {name: tuple(values) for name, values in merged["sources"].items()}
    if untracked := sorted(set(sources) - set(track)):
        raise ValueError(f"sources for untracked categories: {', '.join(untracked)}")
    if missing := [name for name in track if not sources.get(name)]:
        raise ValueError(f"no sources for: {', '.join(missing)} (use manual)")
    values = {value for listed in sources.values() for value in listed}
    if bad := sorted(value for value in values if not SOURCE_VALUE.fullmatch(value)):
        raise ValueError(f"source names must be lowercase-hyphenated: {', '.join(bad)}")
    if not CURRENCY.fullmatch(str(merged["home_currency"])):
        raise ValueError("home_currency must be an ISO 4217 code, e.g. EUR")
    budgets = merged["budgets"]
    if not all(isinstance(amount, int | float) for amount in budgets.values()):
        raise ValueError('budgets must be amounts, e.g. {"groceries": 400}')
    location = merged["location"]
    return Answers(
        timezone=merged["timezone"],
        period=one_of("period", merged["period"], PERIODS),
        weight=one_of("weight", merged["weight"], WEIGHTS),
        glucose=one_of("glucose", merged["glucose"], GLUCOSE_UNITS),
        track=tuple(track),
        sources=sources,
        home_currency=merged["home_currency"],
        budgets={name: float(amount) for name, amount in budgets.items()},
        location=None
        if location is None
        else parse_location(", ".join(str(part) for part in location)),
    )


def write_answers(
    config_path: Path,
    document: tomlkit.TOMLDocument,
    answers: Answers,
    labels: Mapping[str, str],
) -> None:
    """Write the answers to config.toml and sources.md.

    Args:
        config_path: config.toml; sources.md goes next to it.
        document: The parsed config.toml, changed in place.
        answers: The answers.
        labels: Label by category name.
    """
    apply_answers(document, answers)
    config_path.write_text(tomlkit.dumps(document), encoding="utf-8")
    write_sources(config_path.parent / "sources.md", sources_block(answers, labels))


def load_document(config_path: Path) -> tuple[tomlkit.TOMLDocument, dict[str, Any]]:
    """Read config.toml for setup, keeping its comments.

    Args:
        config_path: config.toml.

    Returns:
        The editable document and its plain settings.
    """
    with config_path.open(encoding="utf-8") as file:
        document = tomlkit.load(file)
    return document, document.unwrap()


def custom_names(config: Mapping[str, Any]) -> list[str]:
    """List custom metrics setup offers, leaving out the dining out it manages.

    Args:
        config: The whole of config.toml.

    Returns:
        Custom metric names.
    """
    return [name for name in config.get("custom", {}) if name != DINING_OUT]


def run_answers(config_path: Path, answers_path: Path | None) -> str:
    """Write answers an agent gathered, or show the current ones.

    Args:
        config_path: config.toml.
        answers_path: A JSON file of answers, or None to show the current ones.

    Returns:
        What to print: the current answers as JSON, or a summary of what was
        written.

    Raises:
        ValueError: If the answers are wrong; nothing is written then.
    """
    document, config = load_document(config_path)
    current = current_answers(config)
    if answers_path is None:
        return answers_json(current)
    with answers_path.open(encoding="utf-8") as file:
        data = json.load(file)
    names = [category.name for category in CATEGORIES] + custom_names(config)
    answers = answers_from(data, current, names)
    labels = category_labels(config.get("custom", {}))
    write_answers(config_path, document, answers, labels)
    return "Wrote config.toml and sources.md.\n" + "\n".join(summary(answers, labels))


def apply_answers(document: tomlkit.TOMLDocument, answers: Answers) -> None:
    """Write the answers into config.toml, keeping everything else and its comments.

    Args:
        document: The parsed config.toml, changed in place.
        answers: The answers.
    """
    document["timezone"] = answers.timezone
    document["track"] = list(answers.track)
    document.setdefault("display", tomlkit.table())
    document["display"]["weight"] = answers.weight
    document["display"]["glucose"] = answers.glucose
    document.setdefault("dashboard", tomlkit.table())
    document["dashboard"]["period"] = answers.period
    sources = document.setdefault("sources", tomlkit.table())
    for name in list(sources):
        del sources[name]
    for name, values in answers.sources.items():
        sources[name] = list(values)
    if "finances" in answers.track:
        document.setdefault("finances", tomlkit.table())
        document["finances"]["home_currency"] = answers.home_currency
        budgets = tomlkit.inline_table()
        budgets.update(
            {
                name: int(amount) if amount.is_integer() else amount
                for name, amount in answers.budgets.items()
            }
        )
        document["finances"]["budgets"] = budgets
    if answers.location is not None:
        document.setdefault("weather", tomlkit.table())
        document["weather"]["latitude"], document["weather"]["longitude"] = (
            answers.location
        )
    if DINING_OUT in answers.track:
        document.setdefault("custom", tomlkit.table(is_super_table=True))
        if DINING_OUT not in document["custom"]:
            document["custom"][DINING_OUT] = DINING_OUT_METRIC


def guide_link(value: str) -> str:
    """Link a source to its guide, if it has one.

    Args:
        value: The source's value in ``[sources]``.

    Returns:
        A Markdown link, or "none yet".
    """
    if value in GUIDE_BY_SLUG:
        file = GUIDE_BY_SLUG[value].file
        return f"[{file}](docs/sources/{file})"
    if value.startswith("inferred-"):
        return "[inference.md](docs/sources/inference.md)"
    return "none yet"


def sources_block(answers: Answers, labels: Mapping[str, str]) -> str:
    """Write the part of sources.md that comes from the answers.

    Args:
        answers: The answers.
        labels: Label by category name.

    Returns:
        Markdown between the setup markers.
    """
    used = list(
        dict.fromkeys(value for values in answers.sources.values() for value in values)
    )
    lines = [
        SOURCES_START,
        "",
        "## Sources",
        "",
        "| Source | Guide | Fills |",
        "| --- | --- | --- |",
    ]
    for value in used:
        fills = [
            labels.get(name, name)
            for name, values in answers.sources.items()
            if value in values
        ]
        lines.append(
            f"| {source_label(value)} | {guide_link(value)} | {', '.join(fills)} |"
        )
    lines += ["", "## Which source wins", ""]
    lines += [
        f"- {labels.get(name, name)}: "
        + " over ".join(source_label(value) for value in values)
        for name, values in answers.sources.items()
        if len(values) > 1
    ] or ["No category has more than one source."]
    lines += ["", SOURCES_END]
    return "\n".join(lines)


def write_sources(path: Path, block: str) -> None:
    """Put the setup block into sources.md, keeping everything outside it.

    Args:
        path: sources.md, which may not exist yet.
        block: The block, markers included.
    """
    text = path.read_text(encoding="utf-8") if path.exists() else SOURCES_INTRO
    if SOURCES_START in text and SOURCES_END in text:
        before, rest = text.split(SOURCES_START, 1)
        after = rest.split(SOURCES_END, 1)[1]
        text = before + block + after
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    path.write_text(text, encoding="utf-8")


def run_setup(config_path: Path, prompter: Prompter) -> int:
    """Ask the setup questions, then write config.toml and sources.md on confirmation.

    Args:
        config_path: config.toml; sources.md goes next to it.
        prompter: Asks the questions.

    Returns:
        0, written or not.
    """
    document, config = load_document(config_path)
    labels = category_labels(config.get("custom", {}))
    prompter.heading(
        "dotlife setup",
        "A few questions about what you track and where it comes from. Your "
        "current answers are already selected. Nothing is written until you "
        "confirm at the end.",
    )
    answers = ask_answers(
        prompter, current_answers(config), custom_names(config), labels
    )
    prompter.heading("All set?")
    for line in summary(answers, labels):
        prompter.say(f"  {line}")
    if any(FROM_REFLECTIONS in values for values in answers.sources.values()):
        prompter.warn(
            "Inferring from reflections needs an AI agent and its fetch skill. "
            "Without one, those metrics stay empty."
        )
    if not prompter.confirm("write", "Write config.toml and sources.md?", True):
        prompter.note("Nothing written.")
        return 0
    write_answers(config_path, document, answers, labels)
    prompter.heading("Done", next_step())
    return 0
