import json
import shutil
import tempfile
import tomllib
import unittest
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotlife.config import all_categories, context_for
from dotlife.setup import (
    FROM_REFLECTIONS,
    SOURCES_END,
    SOURCES_START,
    next_step,
    run_answers,
    run_setup,
    write_sources,
)
from dotlife.terminal import Option

ROOT = Path(__file__).resolve().parent.parent


class Each(list):
    """Answers to a question asked more than once, in order."""


@dataclass
class FakePrompter:
    """Answers setup's questions by name; unanswered ones keep their default.

    Attributes:
        answers: Answer by question key; an ``Each`` gives one answer per asking.
        shown: Every heading, note, warning and line shown.
        asked: Every question key, in order.
    """

    answers: Mapping[str, Any]
    shown: list[str] = field(default_factory=list)
    asked: list[str] = field(default_factory=list)

    def answer(self, key: str, default: Any) -> Any:
        """Return the scripted answer for a question, or its default.

        Args:
            key: The question's key.
            default: What Enter would keep.

        Returns:
            The answer.
        """
        self.asked.append(key)
        value = self.answers.get(key, default)
        if isinstance(value, Each):
            return value.pop(0) if value else default
        return value

    def heading(self, title: str, text: str = "") -> None:
        """Record a heading."""
        self.shown += [title, text]

    def note(self, text: str) -> None:
        """Record a note."""
        self.shown.append(f"Note: {text}")

    def warn(self, text: str) -> None:
        """Record a warning."""
        self.shown.append(f"Warning: {text}")

    def say(self, text: str) -> None:
        """Record a line."""
        self.shown.append(text)

    def select(
        self, key: str, question: str, options: Sequence[Option], default: str
    ) -> str:
        """Answer a single choice."""
        return self.answer(key, default)

    def checkbox(
        self, key: str, question: str, options: Sequence[Option], default: Sequence[str]
    ) -> list[str]:
        """Answer a multiple choice."""
        return list(self.answer(key, list(default)))

    def rank(self, key: str, question: str, options: Sequence[Option]) -> list[str]:
        """Answer a ranking."""
        return list(self.answer(key, [option.value for option in options]))

    def text(
        self, key: str, question: str, default: str, check: Callable[[str], str | None]
    ) -> str:
        """Answer a text question, which must pass its check."""
        value = self.answer(key, default)
        assert check(value) is None, check(value)
        return value

    def confirm(self, key: str, question: str, default: bool) -> bool:
        """Answer yes or no."""
        return self.answer(key, default)


FIRST_RUN = {
    "timezone": "Europe/London",
    "dimensions": ["Body and health", "Mind", "Money", "Context"],
    "categories:Body and health": ["activity", "workouts", "sleep", "body"],
    "categories:Mind": ["mood", "reflections"],
    "categories:Money": ["finances"],
    "categories:Context": ["weather"],
    "location": "51.5072, -0.1276",
    "weight": "lb",
    "currency": "GBP",
    "budgets": "groceries=300, eating_out=120",
    "dining_out": True,
    "sources": ["apple-health", "oura", "jrnl"],
    "other_sources": "Example Bank",
    "rank": ["oura", "apple-health"],
    "review": Each(["mood", "finances", "ok"]),
    "change:mood": [FROM_REFLECTIONS],
    "change:finances": ["example-bank"],
}


class SetupTest(unittest.TestCase):
    """Setup asks, assumes sources, writes config.toml and sources.md, and reruns."""

    def setUp(self):
        """Copy the template config.toml into an empty repo folder."""
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "config.toml"
        shutil.copy(ROOT / "config.toml", self.config)

    def tearDown(self):
        """Delete the repo folder."""
        self.temp.cleanup()

    def run_with(self, answers: Mapping[str, Any]) -> FakePrompter:
        """Run setup with scripted answers.

        Args:
            answers: Answer by question key.

        Returns:
            The prompter, with what was shown and asked.
        """
        fake = FakePrompter(
            {
                key: Each(value) if isinstance(value, Each) else value
                for key, value in answers.items()
            }
        )
        self.assertEqual(run_setup(self.config, fake), 0)
        return fake

    def test_first_run_assumes_sources_and_writes(self):
        """Sources are assumed from the apps picked, ranked, then reviewed."""
        fake = self.run_with(FIRST_RUN)
        config = tomllib.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(config["timezone"], "Europe/London")
        self.assertEqual(config["display"]["weight"], "lb")
        self.assertEqual(
            (config["weather"]["latitude"], config["weather"]["longitude"]),
            (51.51, -0.13),
        )
        self.assertEqual(
            config["finances"]["budgets"], {"groceries": 300, "eating_out": 120}
        )
        self.assertEqual(
            config["sources"],
            {
                "activity": ["oura", "apple-health"],
                "workouts": ["oura", "apple-health"],
                "sleep": ["oura", "apple-health"],
                "body": ["apple-health"],
                "mood": ["inferred-reflections"],
                "reflections": ["jrnl"],
                "finances": ["example-bank"],
                "weather": ["open-meteo"],
                "dining_out": ["inferred-finances"],
            },
        )
        on = {
            category.name
            for category in all_categories(config)
            if context_for(category, config).enabled
        }
        self.assertEqual(on, set(config["sources"]))
        self.assertIn("rank", fake.asked)
        self.assertIn("docs/sources/README.md", fake.shown[-1])
        sources = (self.root / "sources.md").read_text(encoding="utf-8")
        self.assertIn(
            "| Open-Meteo | [weather.md](docs/sources/weather.md) | Weather |", sources
        )
        self.assertIn("- Activity: Oura over Apple Health", sources)
        self.assertIn("| example-bank | none yet | Finances |", sources)

    def test_comments_survive(self):
        """Every comment in the template is still there after setup."""
        self.run_with(FIRST_RUN)
        lines = set(self.config.read_text(encoding="utf-8").splitlines())
        template = (ROOT / "config.toml").read_text(encoding="utf-8").splitlines()
        missing = [
            line for line in template if line.startswith("#") and line not in lines
        ]
        self.assertEqual(missing, [])

    def test_second_run_keeps_every_answer(self):
        """Keeping every default changes nothing."""
        self.run_with(FIRST_RUN)
        config = self.config.read_text(encoding="utf-8")
        sources = (self.root / "sources.md").read_text(encoding="utf-8")
        self.run_with({})
        self.assertEqual(self.config.read_text(encoding="utf-8"), config)
        self.assertEqual(
            (self.root / "sources.md").read_text(encoding="utf-8"), sources
        )

    def test_no_ranking_without_overlap(self):
        """Sources that fill different things aren't ranked."""
        fake = self.run_with(FIRST_RUN | {"sources": ["oura", "jrnl"]})
        self.assertNotIn("rank", fake.asked)

    def test_no_writes_without_confirming(self):
        """Saying no at the end leaves the files as they were."""
        before = self.config.read_text(encoding="utf-8")
        self.run_with({"dimensions": [], "write": False})
        self.assertEqual(self.config.read_text(encoding="utf-8"), before)
        self.assertFalse((self.root / "sources.md").exists())

    def test_inference_is_flagged(self):
        """Choosing AI inference warns that it needs an agent."""
        fake = self.run_with(FIRST_RUN | {"write": False})
        self.assertTrue(
            any(line.startswith("Warning: Inferring") for line in fake.shown)
        )


class AnswersTest(unittest.TestCase):
    """An agent's answers are checked and written like the questionnaire's."""

    def setUp(self):
        """Copy the template config.toml into two empty repo folders."""
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("asked", "agent"):
            (self.root / name).mkdir()
            shutil.copy(ROOT / "config.toml", self.root / name / "config.toml")

    def tearDown(self):
        """Delete the folders."""
        self.temp.cleanup()

    def answer(self, folder: str, data: Mapping[str, Any]) -> str:
        """Write answers to a JSON file and apply them to one folder.

        Args:
            folder: ``asked`` or ``agent``.
            data: The answers.

        Returns:
            What the command printed.
        """
        path = self.root / f"{folder}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return run_answers(self.root / folder / "config.toml", path)

    def test_same_files_as_the_questionnaire(self):
        """Answers printed after the questionnaire recreate its files exactly."""
        asked = self.root / "asked" / "config.toml"
        run_setup(
            asked, FakePrompter(dict(FIRST_RUN, review=Each(FIRST_RUN["review"])))
        )
        printed = json.loads(run_answers(asked, None))
        self.answer("agent", printed)
        for name in ("config.toml", "sources.md"):
            self.assertEqual(
                (self.root / "agent" / name).read_text(encoding="utf-8"),
                (self.root / "asked" / name).read_text(encoding="utf-8"),
            )

    def test_partial_answers_keep_the_rest(self):
        """Keys left out keep their current values."""
        self.answer("agent", {"timezone": "Asia/Tokyo"})
        self.answer("agent", {"track": ["sleep"], "sources": {"sleep": ["oura"]}})
        config = tomllib.loads(
            (self.root / "agent" / "config.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            (config["timezone"], config["track"], config["sources"]),
            ("Asia/Tokyo", ["sleep"], {"sleep": ["oura"]}),
        )

    def test_wrong_answers_are_rejected(self):
        """Each mistake gets a plain message, and nothing is written."""
        before = (self.root / "agent" / "config.toml").read_text(encoding="utf-8")
        cases = {
            "unknown answers: colour": {"colour": "blue"},
            "isn.t an IANA": {"timezone": "Mars/Olympus"},
            "unknown categories: sleeep": {"track": ["sleeep"], "sources": {}},
            "no sources for: sleep": {"track": ["sleep"], "sources": {}},
            "untracked categories: mood": {
                "track": [],
                "sources": {"mood": ["manual"]},
            },
            "lowercase-hyphenated: My Bank": {
                "track": ["finances"],
                "sources": {"finances": ["My Bank"]},
            },
            "period must be one of": {"period": "fortnight"},
            "ISO 4217": {"home_currency": "euro"},
        }
        for message, data in cases.items():
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                self.answer("agent", data)
        after = (self.root / "agent" / "config.toml").read_text(encoding="utf-8")
        self.assertEqual(after, before)


class NextStepTest(unittest.TestCase):
    """The questionnaire ends by pointing to the guides."""

    def test_points_to_the_guides_and_the_skill(self):
        """It names the guides and mentions the agent's setup skill."""
        self.assertIn("docs/sources/README.md", next_step())
        self.assertIn("/setup", next_step())


class SourcesFileTest(unittest.TestCase):
    """sources.md keeps what the skills wrote outside the setup block."""

    def test_block_is_replaced_in_place(self):
        """Text before and after the markers survives a rewrite."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sources.md"
            path.write_text(
                f"# Sources\n\nIntro.\n\n{SOURCES_START}\nold\n{SOURCES_END}\n\n"
                "## Oura\n\nToken in the keychain.\n",
                encoding="utf-8",
            )
            write_sources(path, f"{SOURCES_START}\nnew\n{SOURCES_END}")
            text = path.read_text(encoding="utf-8")
        self.assertIn("Intro.", text)
        self.assertIn("new", text)
        self.assertNotIn("old", text)
        self.assertIn("Token in the keychain.", text)

    def test_comments_after_sources_stay_put(self):
        """A comment above the table after [sources] stays above that table."""
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.toml"
            config.write_text(
                'format_version = 1\ntimezone = "UTC"\n\n[sources]\n'
                'sleep = ["apple-health"]\n\n# Apple Health settings\n'
                '[apple-health]\nexport = "inbox/export.zip"\n',
                encoding="utf-8",
            )
            answers = Path(folder) / "answers.json"
            answers.write_text(
                json.dumps(
                    {
                        "track": ["sleep", "mood"],
                        "sources": {
                            "sleep": ["oura", "apple-health"],
                            "mood": ["manual"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            run_answers(config, answers)
            text = config.read_text(encoding="utf-8")
        self.assertIn(
            'mood = ["manual"]\n\n# Apple Health settings\n[apple-health]\n', text
        )

    def test_example_matches_setup(self):
        """sources.example.md's setup block is what dotlife setup writes for Alice."""
        apple = ["apple-health"]
        answers = {
            "timezone": "Europe/London",
            "track": [
                "activity",
                "workouts",
                "sleep",
                "heart",
                "body",
                "fitness_markers",
                "mindfulness",
                "mood",
                "reflections",
                "weather",
            ],
            "sources": {
                "activity": apple,
                "workouts": apple,
                "sleep": apple,
                "heart": apple,
                "body": [*apple, "manual"],
                "fitness_markers": apple,
                "mindfulness": apple,
                "mood": ["manual", FROM_REFLECTIONS],
                "reflections": ["jrnl"],
                "weather": ["open-meteo"],
            },
            "location": [51.51, -0.13],
        }
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.toml"
            shutil.copy(ROOT / "config.toml", config)
            answers_path = Path(folder) / "answers.json"
            answers_path.write_text(json.dumps(answers), encoding="utf-8")
            run_answers(config, answers_path)
            written = (Path(folder) / "sources.md").read_text(encoding="utf-8")
        example = (ROOT / "sources.example.md").read_text(encoding="utf-8")

        def block(text: str) -> str:
            return SOURCES_START + text.split(SOURCES_START)[1].split(SOURCES_END)[0]

        self.assertEqual(block(example), block(written))
