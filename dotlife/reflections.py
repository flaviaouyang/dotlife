import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

FILE_NAME = re.compile(r"(\d{4})\.txt")
HEADER = re.compile(r"\[([^\]]+)\] ?(.*)")
DEFAULT_TIME_FORMAT = "%Y-%m-%d %H:%M"
DEFAULT_TAG_SYMBOLS = "#@"
STAR = "*"


@dataclass(frozen=True, slots=True)
class Reflection:
    """One short reflection, written at a moment in the day.

    Attributes:
        time: When it was written, in local time.
        text: What was written, tags included, without the star.
        starred: Whether its first line ended with ``*``.
        tags: Its tags, lower-cased as jrnl does, in order of first use, without
            repeats.
        line: The line it starts on in its file.
    """

    time: datetime
    text: str
    starred: bool
    tags: tuple[str, ...]
    line: int

    @property
    def day(self) -> date:
        """The local date it was written on."""
        return self.time.date()


@dataclass(frozen=True, slots=True)
class Parsed:
    """What reading one reflections file found.

    Attributes:
        reflections: The entries, in file order.
        stray_lines: Line numbers of text before the first entry, which belongs to
            no entry.
    """

    reflections: tuple[Reflection, ...]
    stray_lines: tuple[int, ...]


def settings(options: Mapping[str, Any]) -> tuple[str, str]:
    """Read the reflections settings from its config section.

    Args:
        options: The ``[reflections]`` section of config.toml.

    Returns:
        The time format and the tag symbols, with defaults.
    """
    return (
        options.get("time_format", DEFAULT_TIME_FORMAT),
        options.get("tag_symbols", DEFAULT_TAG_SYMBOLS),
    )


def tag_pattern(symbols: str) -> re.Pattern[str]:
    """Build jrnl's pattern for tags: a symbol starting a word, then the word.

    Args:
        symbols: Characters that start a tag, e.g. ``#@``.

    Returns:
        The compiled pattern.

    Example:
        >>> tag_pattern("#@").findall("Dinner with @bob. #food/home, not C#.")
        ['@bob', '#food/home']
    """
    return re.compile(rf"(?<!\S)[{re.escape(symbols)}][-+*#/\w]+")


def header_time(line: str, time_format: str) -> tuple[datetime, str] | None:
    """Read an entry's first line: ``[<time>] text``.

    Args:
        line: A line of the file.
        time_format: The ``strptime`` format of the time in brackets.

    Returns:
        The time and the rest of the line, or None when it doesn't start an entry.
    """
    match = HEADER.fullmatch(line)
    if match is None:
        return None
    try:
        return datetime.strptime(match[1], time_format), match[2]
    except ValueError:
        return None


def parse_reflections(text: str, time_format: str, symbols: str) -> Parsed:
    r"""Split a reflections file into entries, jrnl's plain-text way.

    Each entry starts with ``[<time>] text`` on a line of its own; the lines after
    it belong to it until the next entry. A ``*`` ending the first line stars it, as
    jrnl writes it.

    Args:
        text: The file's contents.
        time_format: The ``strptime`` format of the times in brackets.
        symbols: Characters that start a tag.

    Returns:
        The entries and any stray lines before the first one.

    Example:
        >>> lines = ["[2026-08-24 08:12] Coffee. #work", "[2026-08-24 22:40] Bed *"]
        >>> parsed = parse_reflections("\n".join(lines), "%Y-%m-%d %H:%M", "#@")
        >>> [(r.time.hour, r.text, r.starred, r.tags) for r in parsed.reflections]
        [(8, 'Coffee. #work', False, ('#work',)), (22, 'Bed', True, ())]
    """
    tags = tag_pattern(symbols)
    starts: list[tuple[int, datetime, list[str]]] = []
    stray: list[int] = []
    for number, line in enumerate(text.splitlines(), start=1):
        header = header_time(line, time_format)
        if header is not None:
            starts.append((number, header[0], [header[1]]))
        elif starts:
            starts[-1][2].append(line)
        elif line.strip():
            stray.append(number)
    reflections = []
    for number, time, (title, *rest) in starts:
        title = title.rstrip()
        starred = title == STAR or title.endswith(f" {STAR}")
        title = title.removesuffix(STAR).rstrip() if starred else title
        body = "\n".join([title, *rest]).strip()
        reflections.append(
            Reflection(
                time,
                body,
                starred,
                tuple(dict.fromkeys(tag.lower() for tag in tags.findall(body))),
                number,
            )
        )
    return Parsed(tuple(reflections), tuple(stray))


def file_year(name: str) -> int | None:
    """Return the year a reflections file is named after.

    Args:
        name: A file name, e.g. ``2026.txt``.

    Returns:
        The year, or None when the name isn't ``YYYY.txt``.
    """
    match = FILE_NAME.fullmatch(name)
    return None if match is None else int(match[1])


def read_reflections(
    folder: Path, options: Mapping[str, Any]
) -> tuple[Reflection, ...]:
    """Read every correctly named yearly file in a reflections folder.

    Files not named ``YYYY.txt`` are skipped; the validator reports them.

    Args:
        folder: The reflections folder.
        options: The ``[reflections]`` section of config.toml.

    Returns:
        All entries, oldest first.
    """
    time_format, symbols = settings(options)
    found: list[Reflection] = []
    for path in sorted(folder.iterdir()):
        if file_year(path.name) is None:
            continue
        with path.open(encoding="utf-8") as file:
            found.extend(
                parse_reflections(file.read(), time_format, symbols).reflections
            )
    return tuple(sorted(found, key=lambda reflection: reflection.time))
