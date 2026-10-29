import unittest
from collections.abc import Iterator

from dotlife.terminal import Kind, LinePrompter, Menu, Option, Style, render

FRUIT = [
    Option("apple", "Apple", "Red or green"),
    Option("pear", "Pear"),
    Option("fig", "Fig"),
]


def press(menu: Menu, *keys: str) -> bool:
    """Press keys on a menu.

    Args:
        menu: The menu.
        *keys: The keys, in order.

    Returns:
        Whether the last key finished it.
    """
    return [menu.handle(key) for key in keys][-1]


class MenuTest(unittest.TestCase):
    """Menus move, tick and reorder with keys, and draw what they hold."""

    def test_select(self):
        """Down moves the highlight; enter chooses; the cursor stops at the ends."""
        menu = Menu(Kind.SELECT, list(FRUIT))
        self.assertTrue(press(menu, "down", "down", "down", "enter"))
        self.assertEqual(menu.result, ["fig"])

    def test_checkbox(self):
        """Space ticks and unticks; a ticks all, then none; the order is kept."""
        menu = Menu(Kind.CHECKBOX, list(FRUIT))
        press(menu, "down", "down", "space", "up", "up", "space")
        self.assertEqual(menu.result, ["apple", "fig"])
        press(menu, "a")
        self.assertEqual(menu.result, ["apple", "pear", "fig"])
        press(menu, "a")
        self.assertEqual(menu.result, [])

    def test_rank(self):
        """Space picks an item up, arrows carry it, space puts it down."""
        menu = Menu(Kind.RANK, list(FRUIT))
        press(menu, "down", "down", "space", "up", "up", "space", "down")
        self.assertEqual(menu.result, ["fig", "apple", "pear"])
        self.assertFalse(menu.holding)

    def test_render(self):
        """Ticks, the highlight's hint and the keys to use are drawn."""
        menu = Menu(Kind.CHECKBOX, list(FRUIT), ticked={"pear"})
        lines = render(menu, "Which fruit?", Style(color=False))
        self.assertEqual(
            lines[:4], ["Which fruit?", "> [ ] Apple", "  [x] Pear", "  [ ] Fig"]
        )
        self.assertEqual(lines[4], "  Red or green")
        self.assertIn("space to tick", lines[5])


def typed(*answers: str) -> Iterator[str]:
    """Return answers to type, then Enter forever.

    Args:
        *answers: What to type, in order.

    Returns:
        An iterator of typed lines.
    """
    yield from answers
    while True:
        yield ""


class LinePrompterTest(unittest.TestCase):
    """The numbered fallback asks again until the answer makes sense."""

    def prompter(self, *answers: str) -> tuple[LinePrompter, list[str]]:
        """Build a prompter that types the answers and records output.

        Args:
            *answers: What to type.

        Returns:
            The prompter and the lines it showed.
        """
        keys, shown = typed(*answers), []
        return LinePrompter(
            Style(color=False), lambda _: next(keys), shown.append
        ), shown

    def test_select_and_retry(self):
        """A wrong number is explained, then a right one is taken."""
        prompter, shown = self.prompter("7", "2")
        self.assertEqual(prompter.select("k", "Which?", FRUIT, "apple"), "pear")
        self.assertIn("Type a number from 1 to 3.", shown)

    def test_checkbox_and_rank(self):
        """Ticks come back in list order; a ranking puts the rest last."""
        prompter, _ = self.prompter("3 1", "3")
        self.assertEqual(prompter.checkbox("k", "Which?", FRUIT, []), ["apple", "fig"])
        self.assertEqual(prompter.rank("k", "Order", FRUIT), ["fig", "apple", "pear"])

    def test_text_and_confirm(self):
        """Text is checked; Enter keeps defaults."""
        prompter, shown = self.prompter("bad", "good", "")
        check = lambda text: None if text == "good" else "Not good."  # noqa: E731
        self.assertEqual(prompter.text("k", "Word", "", check), "good")
        self.assertIn("Not good.", shown)
        self.assertTrue(prompter.confirm("k", "Sure?", True))
