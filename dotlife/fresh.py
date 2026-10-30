import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from dotlife.config import CONFIG_ENV, DATA_ENV, find_data
from dotlife.staging import merge
from dotlife.validate import Report, format_text, validate_folder

LOG_FILE = Path(".dotlife") / "fresh.log"


@dataclass(frozen=True, slots=True)
class Step:
    """One step of ``make fresh``, as listed under ``[[fresh.steps]]`` in config.toml.

    Attributes:
        name: A short name for messages and ``--only``, e.g. ``oura``.
        argv: The command to run, from the folder holding config.toml; empty for a
            step left to the person's agent.
        instructions: For a step only an AI agent can do (a connector, or
            inference), the file the agent follows; None for a script.
    """

    name: str
    argv: tuple[str, ...]
    instructions: str | None = None

    @property
    def needs_agent(self) -> bool:
        """Whether the step is left to the person's agent and its fetch skill."""
        return self.instructions is not None


@dataclass(frozen=True, slots=True)
class Outcome:
    """How one step went.

    Attributes:
        step: The step.
        exit_code: Its exit code; 0 means it finished.
    """

    step: Step
    exit_code: int

    @property
    def ok(self) -> bool:
        """Whether the step finished without failing."""
        return self.exit_code == 0


def parse_step(entry: Mapping[str, Any], index: int) -> Step:
    """Read one ``[[fresh.steps]]`` table.

    Args:
        entry: The table.
        index: Its position, from 1, for error messages.

    Returns:
        The step. A ``script`` runs with the Python running dotlife; a ``command``
        runs as written; an ``agent`` step names the instructions its agent follows.

    Raises:
        ValueError: If the name is missing, or it doesn't have exactly one of
            ``script``, ``command`` and ``agent``.
    """
    name = entry.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"step {index} in [[fresh.steps]] needs a name")
    runners = [key for key in ("script", "command", "agent") if key in entry]
    if len(runners) != 1:
        raise ValueError(f"step {name!r} needs exactly one of script, command, agent")
    script, command, agent = (
        entry.get("script"),
        entry.get("command"),
        entry.get("agent"),
    )
    if agent is not None:
        if not isinstance(agent, str):
            raise ValueError(f"step {name!r}: agent must be a path, e.g. prompts/x.md")
        return Step(name, (), agent)
    if script is not None:
        if not isinstance(script, str):
            raise ValueError(f"step {name!r}: script must be a path, e.g. scripts/x.py")
        return Step(name, (sys.executable, script))
    if not isinstance(command, list) or not command:
        raise ValueError(f"step {name!r}: command must be a list, e.g. ['swift', 'x']")
    return Step(name, tuple(str(part) for part in command))


def fresh_steps(config: Mapping[str, Any]) -> list[Step]:
    """Read the steps ``make fresh`` runs.

    Args:
        config: The whole of config.toml.

    Returns:
        The steps, in order.

    Raises:
        ValueError: If a step is malformed or two share a name.
    """
    steps = [
        parse_step(entry, index)
        for index, entry in enumerate(config.get("fresh", {}).get("steps", []), 1)
    ]
    names = [step.name for step in steps]
    if repeated := sorted({name for name in names if names.count(name) > 1}):
        raise ValueError(f"step names must be unique: {', '.join(repeated)}")
    return steps


def run_step(step: Step, cwd: Path, env: Mapping[str, str], log: TextIO) -> Outcome:
    """Run one step, showing its output and copying it to the log.

    Args:
        step: The step.
        cwd: The folder holding config.toml.
        env: The environment, with the dotlife variables set.
        log: The open log file.

    Returns:
        How it went. A command that can't start counts as failed.
    """
    try:
        with subprocess.Popen(
            step.argv,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as process:
            for line in process.stdout or ():
                print(f"  {line}", end="")
                log.write(line)
    except OSError as error:
        message = f"couldn't start {step.argv[0]}: {error.strerror}\n"
        print(f"  {message}", end="")
        log.write(message)
        return Outcome(step, 127)
    return Outcome(step, process.returncode)


def summary(outcomes: Sequence[Outcome], report: Report) -> str:
    """Say in a line how the run went.

    Args:
        outcomes: Each step's outcome.
        report: The validator's report.

    Returns:
        One line, e.g. "2 of 3 steps finished; 1 failed: oura. Validation: 0
        errors.".
    """
    ran = [outcome for outcome in outcomes if not outcome.step.needs_agent]
    left = [outcome.step.name for outcome in outcomes if outcome.step.needs_agent]
    failed = [outcome.step.name for outcome in ran if not outcome.ok]
    steps = f"{len(ran) - len(failed)} of {len(ran)} steps finished"
    if failed:
        steps += f"; {len(failed)} failed: {', '.join(failed)}"
    if left:
        steps += f"; {len(left)} for your agent's fetch skill: {', '.join(left)}"
    errors = report.error_count
    return f"{steps}. Validation: {errors} {'error' if errors == 1 else 'errors'}."


def merge_staged(data: Path, config: Mapping[str, Any]) -> list[str]:
    """Merge what the steps staged into the data files, so later steps read them.

    Args:
        data: The data folder.
        config: The whole of config.toml.

    Returns:
        What was merged, or why the merge was skipped.
    """
    try:
        return merge(data, config)
    except ValueError as error:
        return [f"skipped: {error}"]


def run_fresh(
    config_path: Path, config: Mapping[str, Any], steps: Sequence[Step]
) -> int:
    """Run the steps in order, merging what each staged, then validate the data folder.

    Every step runs even when one fails, since sources don't depend on each other.
    Steps that need an AI agent are listed, not run: the fetch skill does them.

    Args:
        config_path: Path to config.toml; steps run in its folder.
        config: Its settings.
        steps: The steps to run.

    Returns:
        0 when every step finished and the data has no errors, 1 otherwise.
    """
    root = config_path.resolve().parent
    data = root / config.get("data_dir", "data")
    data.mkdir(parents=True, exist_ok=True)
    env = os.environ | {CONFIG_ENV: str(config_path.resolve()), DATA_ENV: str(data)}
    log_path = root / LOG_FILE
    log_path.parent.mkdir(exist_ok=True)
    outcomes = []
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"dotlife fresh, {datetime.now():%Y-%m-%d %H:%M}\n")
        for step in steps:
            print(f"{step.name}:")
            if step.needs_agent:
                note = (
                    "not run here: your agent's fetch skill does it, following "
                    f"{step.instructions}"
                )
                print(f"  {note}")
                log.write(f"\n== {step.name}: {note}\n")
                outcomes.append(Outcome(step, 0))
                continue
            log.write(f"\n== {step.name}: {' '.join(step.argv)}\n")
            outcome = run_step(step, root, env, log)
            if not outcome.ok:
                print(f"  failed (exit code {outcome.exit_code})")
                log.write(f"failed (exit code {outcome.exit_code})\n")
            outcomes.append(outcome)
            merge_staged(data, config)
        merged = merge_staged(data, config)
        if merged:
            print("merge:")
            log.write("\n== merge\n")
        for line in merged:
            print(f"  {line}")
            log.write(f"{line}\n")
        source = find_data(config_path)
        report = validate_folder(source.folder, source.config)
        text = format_text(report)
        line = summary(outcomes, report)
        log.write(f"\n{text}\n{line}\n")
    print(f"\n{text}\n{line}\nLog: {LOG_FILE}")
    return (
        0 if all(outcome.ok for outcome in outcomes) and not report.error_count else 1
    )
