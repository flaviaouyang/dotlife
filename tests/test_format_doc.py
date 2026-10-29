import unittest

from dotlife.categories import ACTIVITY, MOOD
from dotlife.format_doc import (
    END_MARKER,
    FORMAT_DOC,
    START_MARKER,
    limits,
    replace_generated,
    updated_format_doc,
)


class FormatDocTest(unittest.TestCase):
    """FORMAT.md's category tables match the specs in the code."""

    def test_format_doc_is_up_to_date(self):
        """The committed FORMAT.md equals a fresh render; run `make docs` if not."""
        with FORMAT_DOC.open(encoding="utf-8") as file:
            self.assertEqual(file.read(), updated_format_doc())

    def test_replaces_only_between_markers(self):
        """Text outside the markers is kept; text between them is replaced."""
        document = f"before\n{START_MARKER}\nold\n{END_MARKER}\nafter\n"
        self.assertEqual(
            replace_generated(document, "new"),
            f"before\n{START_MARKER}\n\nnew\n\n{END_MARKER}\nafter\n",
        )

    def test_missing_markers(self):
        """A document without both markers raises a message naming them."""
        for document in ("no markers", END_MARKER + START_MARKER):
            with (
                self.subTest(document=document),
                self.assertRaisesRegex(ValueError, "markers"),
            ):
                replace_generated(document, "new")

    def test_limits(self):
        """Limits read naturally for both, one or no bounds."""
        self.assertEqual(limits(MOOD.metrics[0]), "1 to 5")
        self.assertEqual(limits(ACTIVITY.metrics[0]), "at least 0")


if __name__ == "__main__":
    unittest.main()
