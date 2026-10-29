import argparse
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dotlife.config import load_config
from dotlife.validate import format_json, format_text, validate_folder

EXIT_OK, EXIT_ERRORS, EXIT_USAGE = 0, 1, 2


def resolve_data_dir(
    config_path: Path, config: Mapping[str, Any], explicit: Path | None
) -> Path:
    """Pick the folder to read: the one given, else ``data_dir``, else ``sample/``.

    Args:
        config_path: Path to config.toml; ``data_dir`` is relative to its folder.
        config: The whole of config.toml.
        explicit: A folder given on the command line, or None.

    Returns:
        The data folder.

    Raises:
        FileNotFoundError: If no candidate folder exists.
    """
    if explicit is not None:
        if not explicit.is_dir():
            raise FileNotFoundError(f"{explicit} is not a folder")
        return explicit
    base = config_path.parent
    data_dir = base / config.get("data_dir", "data")
    if data_dir.is_dir():
        return data_dir
    sample = base / "sample"
    if sample.is_dir():
        print(f"{data_dir} doesn't exist yet; using the sample data.", file=sys.stderr)
        return sample
    raise FileNotFoundError(f"neither {data_dir} nor {sample} exists")


def run_validate(args: argparse.Namespace) -> int:
    """Validate a data folder and print the report.

    Args:
        args: Parsed arguments: ``config``, ``data_dir`` and ``json``.

    Returns:
        0 when there are no errors, 1 when there are, 2 when the config or folder
        can't be read.
    """
    try:
        config = load_config(args.config)
        data_dir = resolve_data_dir(args.config, config, args.data_dir)
    except (FileNotFoundError, tomllib.TOMLDecodeError) as error:
        print(f"dotlife: {error}", file=sys.stderr)
        return EXIT_USAGE
    report = validate_folder(data_dir, config)
    print(format_json(report) if args.json else format_text(report))
    return EXIT_ERRORS if report.error_count else EXIT_OK


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
    validate.add_argument(
        "data_dir",
        nargs="?",
        type=Path,
        help="folder to check (default: data_dir in config.toml, else sample/)",
    )
    validate.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="path to config.toml (default: ./config.toml)",
    )
    validate.add_argument(
        "--json", action="store_true", help="print the report as JSON"
    )
    validate.set_defaults(handler=run_validate)
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
