import os
import shutil
import sys
import textwrap
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, TextIO

ESCAPE = "\x1b"
WINDOWS_KEYS = {"H": "up", "P": "down", "K": "left", "M": "right"}
UNIX_KEYS = {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}


@dataclass(frozen=True, slots=True)
class Option:
    """One choice in a menu.

    Attributes:
        value: What the menu returns for it.
        label: What the person sees.
        hint: A line shown while the choice is highlighted; may be empty.
    """

    value: str
    label: str
    hint: str = ""


class Kind(StrEnum):
    """What a menu asks for."""

    SELECT = "select"
    CHECKBOX = "checkbox"
    RANK = "rank"


@dataclass(frozen=True, slots=True)
class Style:
    """Colours and emphasis, or plain text when colour is off.

    Attributes:
        color: Whether to use ANSI colour codes.
    """

    color: bool

    def wrap(self, text: str, code: str) -> str:
        """Apply an ANSI style code.

        Args:
            text: The text.
            code: The SGR code, e.g. ``1`` for bold.

        Returns:
            The styled text, or the text as it is when colour is off.
        """
        return f"\x1b[{code}m{text}\x1b[0m" if self.color else text

    def bold(self, text: str) -> str:
        """Return the text in bold."""
        return self.wrap(text, "1")

    def dim(self, text: str) -> str:
        """Return the text faint, for hints and kept answers."""
        return self.wrap(text, "2")

    def accent(self, text: str) -> str:
        """Return the text in the accent colour, for the cursor and answers."""
        return self.wrap(text, "36")

    def hint(self, text: str) -> str:
        """Return the text in magenta, for what the highlighted choice means."""
        return self.wrap(text, "35")

    def good(self, text: str) -> str:
        """Return the text in green."""
        return self.wrap(text, "32")

    def caution(self, text: str) -> str:
        """Return the text in yellow, for notes."""
        return self.wrap(text, "33")

    def bad(self, text: str) -> str:
        """Return the text in red, for problems."""
        return self.wrap(text, "31")


def wants_color(stream: TextIO) -> bool:
    """Decide whether to colour output, honouring NO_COLOR.

    Args:
        stream: Where output goes.

    Returns:
        True for a terminal without NO_COLOR set.
    """
    return stream.isatty() and "NO_COLOR" not in os.environ


NEXT = Option("next", "Next", "Done picking; move on to the next part.")


@dataclass(slots=True)
class Menu:
    """The state of an arrow-key menu, separate from the terminal so it can be tested.

    Attributes:
        kind: Select one, tick several, or put in order.
        options: The choices, in the order shown; for ranking, the current order.
        cursor: The highlighted position.
        ticked: For checkboxes, the ticked values.
        holding: For ranking, whether the highlighted item moves with the cursor.
    """

    kind: Kind
    options: list[Option]
    cursor: int = 0
    ticked: set[str] = field(default_factory=set)
    holding: bool = False

    @property
    def rows(self) -> list[Option]:
        """What is drawn: the options, and for checkboxes a last row, Next."""
        return [*self.options, NEXT] if self.kind is Kind.CHECKBOX else self.options

    def handle(self, key: str) -> bool:
        """Apply one key press.

        Args:
            key: ``up``, ``down``, ``space``, ``enter``, or a character.

        Returns:
            True when the menu is finished.
        """
        last = len(self.rows) - 1
        if key in ("up", "k", "down", "j"):
            step = -1 if key in ("up", "k") else 1
            target = min(max(self.cursor + step, 0), last)
            if self.kind is Kind.RANK and self.holding:
                self.options[self.cursor], self.options[target] = (
                    self.options[target],
                    self.options[self.cursor],
                )
            self.cursor = target
            return False
        if self.kind is Kind.CHECKBOX and key in ("enter", "space"):
            if self.cursor == last:
                return key == "enter"
            self.toggle()
            return False
        if key == "space":
            self.toggle()
            return False
        if key == "a" and self.kind is Kind.CHECKBOX:
            values = {option.value for option in self.options}
            self.ticked = set() if self.ticked == values else values
            return False
        return key == "enter"

    def toggle(self) -> None:
        """Tick or untick the highlighted choice, or pick it up or put it down."""
        if self.kind is Kind.CHECKBOX:
            self.ticked ^= {self.options[self.cursor].value}
        elif self.kind is Kind.RANK:
            self.holding = not self.holding

    @property
    def result(self) -> list[str]:
        """The answer: the highlighted value, the ticked ones, or the order."""
        if self.kind is Kind.SELECT:
            return [self.options[self.cursor].value]
        if self.kind is Kind.CHECKBOX:
            return [
                option.value for option in self.options if option.value in self.ticked
            ]
        return [option.value for option in self.options]


HELP = {
    Kind.SELECT: "up/down to move, enter to choose",
    Kind.CHECKBOX: "up/down to move, enter to tick, a for all, choose Next when done",
    Kind.RANK: "up/down to move, space to pick up or put down, enter when done",
}


def fit(text: str, width: int) -> str:
    """Cut text to a width, so a line never wraps and breaks the redraw.

    Args:
        text: Plain text, without colour codes.
        width: The most characters allowed.

    Returns:
        The text, ending in "..." if it was cut.
    """
    return text if len(text) <= width else text[: max(width - 3, 0)] + "..."


def wrap(text: str) -> str:
    """Wrap prose at word boundaries to the terminal's width, at most 88 columns.

    Args:
        text: A paragraph.

    Returns:
        The paragraph, with line breaks.
    """
    return textwrap.fill(text, min(shutil.get_terminal_size().columns, 88) - 1)


def render(menu: Menu, question: str, style: Style, width: int = 80) -> list[str]:
    """Draw a menu as lines of text.

    Args:
        menu: Its state.
        question: The question above it.
        style: Colours.
        width: The terminal's width; longer lines are cut.

    Returns:
        The lines, ending with the highlighted choice's hint in its own colour, then
        the keys to use, dimmed.
    """
    lines = [style.bold(fit(question, width - 1))]
    for index, option in enumerate(menu.rows):
        here = index == menu.cursor
        pointer = style.accent(">") if here else " "
        if menu.kind is Kind.CHECKBOX and option is NEXT:
            mark = "    "
        elif menu.kind is Kind.CHECKBOX:
            box = style.good("[x]") if option.value in menu.ticked else "[ ]"
            mark = f"{box} "
        elif menu.kind is Kind.RANK:
            mark = f"{index + 1}. "
        else:
            mark = ""
        label = fit(
            option.label + ("  (moving)" if here and menu.holding else ""),
            width - 3 - (4 if menu.kind is Kind.CHECKBOX else len(mark)),
        )
        if here:
            label = style.accent(label)
        lines.append(f"{pointer} {mark}{label}")
    hint = fit(menu.rows[menu.cursor].hint, width - 3)
    keys = fit(HELP[menu.kind], width - 3)
    lines += [style.hint(f"  {hint}") if hint else "", "", style.dim(f"  {keys}")]
    return lines


class Prompter(Protocol):
    """Asks the setup questions; terminal menus, numbered prompts, or a test double."""

    def heading(self, title: str, text: str = "") -> None:
        """Start a section with a title and an optional explanation."""
        ...

    def note(self, text: str) -> None:
        """Show something worth knowing."""
        ...

    def warn(self, text: str) -> None:
        """Show something that needs attention."""
        ...

    def say(self, text: str) -> None:
        """Show a plain line."""
        ...

    def select(
        self, key: str, question: str, options: Sequence[Option], default: str
    ) -> str:
        """Ask for one choice; ``key`` names the question for tests."""
        ...

    def checkbox(
        self, key: str, question: str, options: Sequence[Option], default: Sequence[str]
    ) -> list[str]:
        """Ask for any number of choices."""
        ...

    def rank(self, key: str, question: str, options: Sequence[Option]) -> list[str]:
        """Ask to put choices in order, best first."""
        ...

    def text(
        self, key: str, question: str, default: str, check: Callable[[str], str | None]
    ) -> str:
        """Ask for a line of text until ``check`` returns None."""
        ...

    def confirm(self, key: str, question: str, default: bool) -> bool:
        """Ask yes or no."""
        ...


@dataclass(frozen=True, slots=True)
class LinePrompter:
    """Asks with numbered choices, line by line: for pipes, CI and plain terminals.

    Attributes:
        style: Colours.
        ask: Shows a prompt and returns what was typed.
        say_line: Shows a line.
    """

    style: Style
    ask: Callable[[str], str] = input
    say_line: Callable[[str], None] = print

    def heading(self, title: str, text: str = "") -> None:
        """Start a section with a title and an optional explanation."""
        self.say_line("")
        self.say_line(self.style.bold(self.style.accent(f"== {title}")))
        if text:
            self.say_line(self.style.dim(wrap(text)))

    def note(self, text: str) -> None:
        """Show something worth knowing."""
        first, _, rest = wrap(f"Note: {text}").partition("Note:")
        self.say_line(f"{first}{self.style.caution('Note:')}{rest}")

    def warn(self, text: str) -> None:
        """Show something that needs attention."""
        first, _, rest = wrap(f"Warning: {text}").partition("Warning:")
        self.say_line(f"{first}{self.style.bad('Warning:')}{rest}")

    def say(self, text: str) -> None:
        """Show a plain line."""
        self.say_line(text)

    def numbered(self, question: str, options: Sequence[Option]) -> None:
        """Show a question and its numbered choices, with hints.

        Args:
            question: The question.
            options: The choices.
        """
        self.say_line("")
        self.say_line(self.style.bold(question))
        for number, option in enumerate(options, 1):
            hint = f"  {self.style.dim(option.hint)}" if option.hint else ""
            self.say_line(f"  {number:>2}. {option.label}{hint}")

    def numbers(self, typed: str, count: int) -> list[int] | None:
        """Read typed numbers.

        Args:
            typed: E.g. ``2 1 3``.
            count: How many choices there are.

        Returns:
            The zero-based positions, in order, or None if any is wrong.
        """
        words = typed.replace(",", " ").split()
        if not all(word.isdigit() and 1 <= int(word) <= count for word in words):
            return None
        return list(dict.fromkeys(int(word) - 1 for word in words))

    def select(
        self, key: str, question: str, options: Sequence[Option], default: str
    ) -> str:
        """Ask for one choice by number."""
        self.numbered(question, options)
        values = [option.value for option in options]
        while True:
            typed = self.ask(f"Choose 1-{len(options)} [{values.index(default) + 1}]: ")
            if not typed.strip():
                return default
            picked = self.numbers(typed, len(options))
            if picked is not None and len(picked) == 1:
                return values[picked[0]]
            self.say_line(self.style.bad(f"Type a number from 1 to {len(options)}."))

    def checkbox(
        self, key: str, question: str, options: Sequence[Option], default: Sequence[str]
    ) -> list[str]:
        """Ask for any number of choices by number; all, none or Enter work too."""
        self.numbered(question, options)
        values = [option.value for option in options]
        shown = " ".join(str(values.index(value) + 1) for value in default) or "none"
        while True:
            typed = self.ask(f"Numbers, e.g. 1 3, or all or none [{shown}]: ").strip()
            if not typed:
                return list(default)
            if typed in ("all", "none"):
                return values if typed == "all" else []
            picked = self.numbers(typed, len(options))
            if picked is not None:
                return [values[index] for index in sorted(picked)]
            self.say_line(self.style.bad(f"Type numbers from 1 to {len(options)}."))

    def rank(self, key: str, question: str, options: Sequence[Option]) -> list[str]:
        """Ask for an order by typing numbers, best first; missing ones go last."""
        self.numbered(question, options)
        values = [option.value for option in options]
        while True:
            typed = self.ask("Numbers, best first [keep this order]: ").strip()
            picked = self.numbers(typed, len(options))
            if picked is not None:
                rest = [index for index in range(len(values)) if index not in picked]
                return [values[index] for index in [*picked, *rest]]
            self.say_line(self.style.bad(f"Type numbers from 1 to {len(options)}."))

    def text(
        self, key: str, question: str, default: str, check: Callable[[str], str | None]
    ) -> str:
        """Ask for a line of text until it passes the check."""
        while True:
            shown = f" [{default}]" if default else ""
            typed = (
                self.ask(f"\n{self.style.bold(question)}{shown}: ").strip() or default
            )
            problem = check(typed)
            if problem is None:
                return typed
            self.say_line(self.style.bad(problem))

    def confirm(self, key: str, question: str, default: bool) -> bool:
        """Ask yes or no."""
        while True:
            hint = "Y/n" if default else "y/N"
            typed = (
                self.ask(f"\n{self.style.bold(question)} [{hint}]: ").strip().lower()
            )
            if not typed:
                return default
            if typed in ("y", "yes", "n", "no"):
                return typed.startswith("y")
            self.say_line(self.style.bad("Type y or n."))


@contextmanager
def key_reader() -> Iterator[Callable[[], str]]:
    """Read single key presses from the terminal until the block ends.

    Yields:
        A function returning the next key: ``up``, ``down``, ``left``, ``right``,
        ``space``, ``enter``, ``escape``, or the character typed.
    """
    if os.name == "nt":
        import msvcrt

        def read_windows() -> str:
            char = msvcrt.getwch()
            if char in ("\x00", "\xe0"):
                return WINDOWS_KEYS.get(msvcrt.getwch(), "")
            return name_of(char)

        yield read_windows
        return
    import select
    import termios
    import tty

    descriptor = sys.stdin.fileno()
    saved = termios.tcgetattr(descriptor)
    tty.setcbreak(descriptor)

    def read_unix() -> str:
        char = os.read(descriptor, 1).decode(errors="ignore")
        if char != ESCAPE:
            return name_of(char)
        if not select.select([descriptor], [], [], 0.05)[0]:
            return "escape"
        return UNIX_KEYS.get(os.read(descriptor, 2).decode(errors="ignore"), "")

    try:
        yield read_unix
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved)


def name_of(char: str) -> str:
    """Name a typed character.

    Args:
        char: One character.

    Returns:
        ``space``, ``enter``, or the character itself.

    Raises:
        KeyboardInterrupt: For Ctrl+C, which raw input on Windows doesn't raise.
    """
    if char == "\x03":
        raise KeyboardInterrupt
    return {" ": "space", "\r": "enter", "\n": "enter"}.get(char, char)


@dataclass(frozen=True, slots=True)
class TerminalPrompter:
    """Asks with arrow-key menus, like a modern command-line tool.

    Attributes:
        style: Colours.
        lines: Asks typed questions (text and the fallback), sharing ``style``.
        out: Where menus are drawn.
    """

    style: Style
    lines: LinePrompter
    out: TextIO = sys.stdout

    def heading(self, title: str, text: str = "") -> None:
        """Start a section with a title and an optional explanation."""
        self.lines.heading(title, text)

    def note(self, text: str) -> None:
        """Show something worth knowing."""
        self.lines.note(text)

    def warn(self, text: str) -> None:
        """Show something that needs attention."""
        self.lines.warn(text)

    def say(self, text: str) -> None:
        """Show a plain line."""
        self.lines.say(text)

    def run(self, menu: Menu, question: str) -> list[str]:
        """Draw a menu and redraw it on every key until it's finished.

        Args:
            menu: Its starting state.
            question: The question above it.

        Returns:
            The menu's result.
        """
        drawn = 0
        self.out.write("\n\x1b[?25l")
        try:
            with key_reader() as read:
                while True:
                    if drawn:
                        self.out.write(f"\x1b[{drawn}F\x1b[J")
                    width = shutil.get_terminal_size().columns
                    lines = render(menu, question, self.style, width)
                    self.out.write("\n".join(lines) + "\n")
                    self.out.flush()
                    drawn = len(lines)
                    if menu.handle(read()):
                        break
        finally:
            self.out.write(f"\x1b[{drawn}F\x1b[J\x1b[?25h" if drawn else "\x1b[?25h")
        labels = {option.value: option.label for option in menu.options}
        answer = ", ".join(labels[value] for value in menu.result) or "none"
        self.out.write(f"{self.style.bold(question)} {self.style.accent(answer)}\n")
        return menu.result

    def select(
        self, key: str, question: str, options: Sequence[Option], default: str
    ) -> str:
        """Ask for one choice with the arrow keys."""
        values = [option.value for option in options]
        start = values.index(default) if default in values else 0
        return self.run(Menu(Kind.SELECT, list(options), start), question)[0]

    def checkbox(
        self, key: str, question: str, options: Sequence[Option], default: Sequence[str]
    ) -> list[str]:
        """Ask for any number of choices with the arrow keys and space."""
        return self.run(
            Menu(Kind.CHECKBOX, list(options), ticked=set(default)), question
        )

    def rank(self, key: str, question: str, options: Sequence[Option]) -> list[str]:
        """Ask to put choices in order by picking them up and moving them."""
        return self.run(Menu(Kind.RANK, list(options)), question)

    def text(
        self, key: str, question: str, default: str, check: Callable[[str], str | None]
    ) -> str:
        """Ask for a line of text."""
        return self.lines.text(key, question, default, check)

    def confirm(self, key: str, question: str, default: bool) -> bool:
        """Ask yes or no with the arrow keys."""
        options = [Option("yes", "Yes"), Option("no", "No")]
        return self.select(key, question, options, "yes" if default else "no") == "yes"


def prompter() -> Prompter:
    """Pick arrow-key menus in a terminal, numbered prompts otherwise.

    Returns:
        The prompter.
    """
    style = Style(wants_color(sys.stdout))
    lines = LinePrompter(style)
    if sys.stdin.isatty() and sys.stdout.isatty():
        return TerminalPrompter(style, lines)
    return lines
