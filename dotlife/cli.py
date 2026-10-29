import argparse
import os
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

from dotlife.config import CONFIG_ENV, DATA_ENV, find_data
from dotlife.validate import format_json, format_text, validate_folder

EXIT_OK, EXIT_ERRORS, EXIT_USAGE = 0, 1, 2
APP = Path(__file__).resolve().parent / "dashboard" / "server.py"


def add_source_arguments(parser: argparse.ArgumentParser, folder_help: str) -> None:
    """Add the data folder and ``--config`` arguments every command shares.

    Args:
        parser: The sub-command's parser.
        folder_help: What the folder is for, e.g. "folder to check".
    """
    parser.add_argument(
        "data_dir",
        nargs="?",
        type=Path,
        help=f"{folder_help} (default: data_dir in config.toml, else sample/); "
        "a config.toml inside it is used instead of --config",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="path to config.toml (default: ./config.toml)",
    )


def run_validate(args: argparse.Namespace) -> int:
    """Validate a data folder and print the report.

    Args:
        args: Parsed arguments: ``config``, ``data_dir`` and ``json``.

    Returns:
        0 when there are no errors, 1 when there are, 2 when the config or folder
        can't be read.
    """
    try:
        source = find_data(args.config, args.data_dir)
    except (FileNotFoundError, tomllib.TOMLDecodeError) as error:
        print(f"dotlife: {error}", file=sys.stderr)
        return EXIT_USAGE
    if source.is_sample:
        print("No data folder yet; checking the sample data.", file=sys.stderr)
    report = validate_folder(source.folder, source.config)
    print(format_json(report) if args.json else format_text(report))
    return EXIT_ERRORS if report.error_count else EXIT_OK


def run_dashboard(args: argparse.Namespace) -> int:
    """Start the Streamlit dashboard and wait until it stops.

    Streamlit runs in the folder holding config.toml, so it finds the theme in
    ``.streamlit/`` there. The app reads the config and data folder from
    environment variables.

    Args:
        args: Parsed arguments: ``config`` and ``data_dir``.

    Returns:
        Streamlit's exit code.
    """
    config = args.config.resolve()
    env = os.environ | {CONFIG_ENV: str(config)}
    if args.data_dir is not None:
        env[DATA_ENV] = str(args.data_dir.resolve())
    command = [sys.executable, "-m", "streamlit", "run", str(APP)]
    return subprocess.run(command, cwd=config.parent, env=env, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the ``dotlife`` command's argument parser.

    Returns:
        The parser, with one sub-command per action.
    """
    parser = argparse.ArgumentParser(
        prog="dotlife", description="A life dashboard built on plain files you own."
    )
    commands = parser.add_subparsers(required=True, metavar="COMMAND")
    validate = commands.add_parser(
        "validate",
        help="check data files against FORMAT.md",
        description="Check data files against FORMAT.md. Reports gaps; fills none.",
    )
    add_source_arguments(validate, "folder to check")
    validate.add_argument(
        "--json", action="store_true", help="print the report as JSON"
    )
    validate.set_defaults(handler=run_validate)
    dashboard = commands.add_parser(
        "dashboard",
        help="open the dashboard in the browser",
        description="Open the dashboard. Stop it with Ctrl+C.",
    )
    add_source_arguments(dashboard, "folder to show")
    dashboard.set_defaults(handler=run_dashboard)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``dotlife`` command.

    Args:
        argv: Arguments without the program name; None reads ``sys.argv``.

    Returns:
        The exit code.
    """
    args = build_parser().parse_args(argv)
    return args.handler(args)
