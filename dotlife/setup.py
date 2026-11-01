import json
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import tomlkit
from tomlkit.items import Table

from dotlife.categories import AREA_OF, AREAS, CATEGORIES
from dotlife.terminal import Option, Prompter
from dotlife.validate import plural

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
    "show_sensitive",
    "other",
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
        period: Which the dashboard opens on, ``week`` or ``month``. Not asked;
            set it in config.toml.
        weight: ``kg`` or ``lb``.
        glucose: ``mmol/L`` or ``mg/dL``.
        track: Categories to track, built-in and custom.
        sources: Per category, its sources, best first.
        home_currency: ISO 4217 code, for finances.
        budgets: Monthly budget per spending category, in the home currency.
        location: Home latitude and longitude for weather, rounded to two
            decimals, or None.
        show_sensitive: Whether the dashboard shows sensitive categories
            without being asked.
        other: The apps, devices or files the person named in their own words
            that no guide covers, for their agent to work out.
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
    show_sensitive: bool = False
    other: str = ""


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
        show_sensitive=config.get("dashboard", {}).get("show_sensitive", False),
        other=config.get("setup", {}).get("other", ""),
    )


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


def ask_timezone(prompter: Prompter, current: Answers) -> str:
    """Ask for the time zone.

    Args:
        prompter: Asks the questions.
        current: The answers so far, for the default.

    Returns:
        The time zone.
    """
    prompter.heading("The basics", "Dates and weeks follow your time zone.")
    return prompter.text(
        "timezone", "Your time zone", current.timezone, timezone_problem
    )


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
            "Sensitive means private: the kind of thing you wouldn't want on screen "
            "while someone looks over your shoulder. They are only tracked if you "
            "say so here."
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
) -> tuple[list[str], str]:
    """Ask which apps and devices the person uses, best first where they overlap.

    Args:
        prompter: Asks the questions.
        current: The answers so far, for defaults.
        track: The categories to track.
        labels: Label by category name.

    Returns:
        Their sources, ranked, and what they said in their own words about apps,
        devices or files no guide covers (empty if nothing).
    """
    prompter.heading(
        "Where your data comes from",
        "These are the apps and devices dotlife has a guide for, limited to what "
        "you chose to track. Tick the ones you use.",
    )
    previous = list(
        dict.fromkeys(value for values in current.sources.values() for value in values)
    )
    relevant = [
        guide
        for guide in GUIDES
        if set(guide.categories) & set(track) and not guide.automatic
    ]
    picked = (
        prompter.checkbox(
            "sources",
            "Which of these do you use?",
            [
                Option(
                    guide.slug,
                    guide.label,
                    "Fills "
                    + ", ".join(
                        labels[name] for name in guide.categories if name in track
                    )
                    + ".",
                )
                for guide in relevant
            ],
            [guide.slug for guide in relevant if guide.slug in previous],
        )
        if relevant
        else []
    )
    unguided = [
        labels[name]
        for name in track
        if name != DINING_OUT and not any(name in guide.categories for guide in GUIDES)
    ]
    if unguided:
        prompter.note(
            f"No guide covers {', '.join(unguided)} yet. You can enter those by "
            "hand, or describe what you use below and your agent will look for a way."
        )
    other = prompter.text(
        "other",
        "Anything else you use? Apps, devices or files, in your own words, or none",
        current.other or "none",
        lambda text: None,
    ).strip()
    pool = sorted(
        picked,
        key=lambda value: previous.index(value) if value in previous else len(previous),
    )
    overlapping = [
        value
        for value in pool
        if any(
            other_value != value
            and set(GUIDE_BY_SLUG[value].categories)
            & set(GUIDE_BY_SLUG[other_value].categories)
            & set(track)
            for other_value in pool
        )
    ]
    ranked = pool
    if len(overlapping) >= 2:
        prompter.note(
            "Some of these record the same things. When two report the same day, the "
            "one ranked higher wins."
        )
        ranked = prompter.rank(
            "rank",
            "Rank them, most trusted first",
            [Option(value, source_label(value)) for value in overlapping],
        )
        ranked += [value for value in pool if value not in ranked]
    return ranked, "" if other.lower() == "none" else other


def assume_sources(
    track: Sequence[str], pool: Sequence[str], current: Answers
) -> dict[str, tuple[str, ...]]:
    """Work out each category's sources from the person's apps and devices.

    A category keeps its previous sources while each is still in use or has no
    guide (an agent added it). Else it gets every ranked source whose guide fills
    it; failing that, a source that needs no account (weather); failing that, by
    hand.

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
        elif previous and all(
            value in usable or value not in GUIDE_BY_SLUG for value in previous
        ):
            sources[name] = previous
        else:
            covering = tuple(
                value for value in pool if name in GUIDE_BY_SLUG[value].categories
            )
            automatic = tuple(
                guide.slug
                for guide in GUIDES
                if guide.automatic and name in guide.categories
            )
            sources[name] = covering or automatic or (MANUAL,)
    return sources


def ask_show_sensitive(
    prompter: Prompter, current: Answers, track: Sequence[str]
) -> bool:
    """Ask whether the dashboard shows sensitive categories without being asked.

    Args:
        prompter: Asks the questions.
        current: The answers so far, for the default.
        track: The categories to track.

    Returns:
        The person's choice; the current one when nothing sensitive is tracked.
    """
    if not any(
        category.sensitive and category.name in track for category in CATEGORIES
    ):
        return current.show_sensitive
    return prompter.confirm(
        "show_sensitive",
        "Show your sensitive categories on the dashboard by default? (Anyone "
        "looking at your screen would see them; you can still toggle it there.)",
        current.show_sensitive,
    )


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
    timezone = ask_timezone(prompter, current)
    names = [
        name
        for dimension in AREAS
        for name in [category.name for category in CATEGORIES] + list(custom)
        if dimension_of(name) == dimension
    ]
    track = ask_categories(prompter, current, names, labels)
    show_sensitive = ask_show_sensitive(prompter, current, track)
    weight, glucose, currency, budgets, dining, location = ask_details(
        prompter, current, track
    )
    if dining:
        track.append(DINING_OUT)
    pool, other = ask_source_pool(prompter, current, track, labels)
    return Answers(
        timezone,
        current.period,
        weight,
        glucose,
        tuple(track),
        assume_sources(track, pool, current),
        currency,
        budgets,
        location,
        show_sensitive,
        other,
    )


def summary(answers: Answers, labels: Mapping[str, str]) -> list[str]:
    """Describe the answers for a last look before writing.

    Args:
        answers: The answers.
        labels: Label by category name.

    Returns:
        Lines to show.
    """
    sources = {value for values in answers.sources.values() for value in values}
    lines = [
        f"Time zone {answers.timezone}, {answers.weight} and {answers.glucose}.",
        f"Tracking {plural(len(answers.track), 'category', 'categories')} from "
        f"{plural(len(sources), 'source')}.",
    ]
    if "finances" in answers.track:
        lines.append(
            f"Currency {answers.home_currency}; "
            f"budgets {budgets_text(answers.budgets)}."
        )
    width = max((len(labels.get(name, name)) for name in answers.sources), default=0)
    lines += [
        f"{labels.get(name, name):<{width}}  "
        + " > ".join(source_label(value) for value in values)
        for name, values in answers.sources.items()
    ]
    if any(values == (MANUAL,) for values in answers.sources.values()):
        lines.append(
            "By hand means no source fills it yet: you type the values in, or your "
            "agent finds a source."
        )
    return lines


def next_step() -> str:
    """Say what to do after the questions.

    Returns:
        A short paragraph.
    """
    return (
        "Next, connect your sources. With an AI coding agent, ask it to run the "
        "setup skill (/setup in Claude Code): it reads your answers and does the "
        "rest. Without one, start at docs/sources/README.md, open the guide for each "
        "source in sources.md, write its script, and list it under [[fresh.steps]] "
        "in config.toml. Then run make fresh."
    )


def finish_setup(config_path: Path) -> str:
    """Delete the demo ``sample/`` folder, the last step of setting up.

    Args:
        config_path: config.toml; ``sample/`` is next to it.

    Returns:
        What was done.

    Raises:
        ValueError: If the person's data folder has no data yet, since the
            dashboard would then have nothing to show but the sample.
    """
    _, config = load_document(config_path)
    root = config_path.parent
    sample = root / "sample"
    if not sample.is_dir():
        return "No sample/ folder; nothing to clean up."
    data = root / config.get("data_dir", "data")
    if data.resolve() == sample.resolve():
        raise ValueError("data_dir in config.toml is sample/; point it at your data")
    if not (any(data.glob("*.csv")) or any(data.glob("reflections/*.txt"))):
        raise ValueError(
            f"{data.name}/ has no data yet, so sample/ stays until make fresh has "
            "filled it"
        )
    shutil.rmtree(sample)
    return (
        "Deleted sample/. The dashboard now shows your data. It stays in git history."
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
            "show_sensitive": answers.show_sensitive,
            "other": answers.other,
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
    if not isinstance(merged["show_sensitive"], bool):
        raise ValueError("show_sensitive must be true or false")
    if not isinstance(merged["other"], str):
        raise ValueError("other must be text, in the person's own words")
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
        show_sensitive=merged["show_sensitive"],
        other=merged["other"].strip(),
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
    document["dashboard"]["show_sensitive"] = answers.show_sensitive
    if answers.other or "setup" in document:
        document.setdefault("setup", tomlkit.table())
        document["setup"]["other"] = answers.other
    replace_sources(document.setdefault("sources", tomlkit.table()), answers.sources)
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


def replace_sources(table: Table, sources: Mapping[str, Sequence[str]]) -> None:
    """Put new keys in ``[sources]``, ahead of the comments that follow the old ones.

    Comments after the last key belong to the next table (e.g. the comment above
    ``[apple-health]``), so the new keys go before them, not after.

    Args:
        table: The ``[sources]`` table, changed in place.
        sources: Per category, its sources, best first.
    """
    for name in list(table):
        del table[name]
    for index, (name, values) in enumerate(sources.items()):
        if index < len(table.value.body):
            table.value._insert_at(index, name, tomlkit.item(list(values)))
        else:
            table[name] = list(values)


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
    if value == MANUAL:
        return "[manual.md](docs/sources/manual.md)"
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
    if answers.other:
        lines += [
            "",
            "## In your own words",
            "",
            "What you said you use that no guide covers. The `setup` skill works out "
            "how to read it.",
            "",
            *(f"> {line}" for line in answers.other.splitlines()),
        ]
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
        "A few plain questions about what you track and the apps you use. Your "
        "answers are kept for dotlife and for your AI agent, which works out the "
        "rest. Your current answers are already selected. Nothing is written until "
        "you confirm at the end.",
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
