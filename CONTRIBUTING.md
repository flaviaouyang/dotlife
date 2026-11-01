# Contributing to dotlife

How to change dotlife itself. The same rules apply to people and to coding agents. To use dotlife with your own data, see `README.md`. Agents working on someone's data follow `AGENTS.md`.

dotlife is a small, open-source life dashboard. Its core is a plain-file data format (`FORMAT.md`). A stdlib-only validator checks the files, a Streamlit dashboard reads only that format, and agent skills fill it from a person's sources.

## Layout

The project is early, so most of these don't exist yet. All project code lives in the `dotlife/` package. The repo root holds the user's files and the docs.

- `FORMAT.md`: the data format spec. Its per-category tables are generated from `dotlife/categories.py` by `make docs`, so change the specs, not the tables. A test fails when the file is out of date.
- `config.toml`: every number and threshold. Code reads it and never hard-codes a value.
- `sources.example.md`: a finished `sources.md` for Alice, made up. A test checks that its setup block is what `dotlife setup` writes; keep the rest in step with the guides.
- `sample/`: the demo data, half a year of Alice (of Alice and Bob), with its own `config.toml`. Every value is made up, and the files are generated, so don't edit them by hand. A test checks that it validates with no errors and only its planted warnings.
- `dotlife/`: the package. Run it with `uv run dotlife <command>`, or `python3 -m dotlife <command>` without installing.
  - `schema.py`: the building blocks: `Field`, `Metric`, `Category` and `Context` (frozen dataclasses) and row parsing.
  - `rules.py`: plug-ins for special behaviour, such as the wake-date check and the watch-off filter. Categories take them as functions, not subclasses.
  - `categories.py`: every category spec, built from the two modules above.
  - `config.py`: reads `config.toml` and gives each category its settings, including overrides of plausible bounds and related metrics.
  - `format_doc.py`: generates the category tables in `FORMAT.md`.
  - `periods.py`: weeks, months and clock-time maths.
  - `reflections.py`: reads the yearly `reflections/YYYY.txt` files (jrnl's plain-text format) into entries with their time, star and tags.
  - `load.py`: reads a data folder once into a `Dataset` (rows by category, settings, reflections).
  - `summaries.py`: the calculations the dashboard shows: daily and period values, clock times, the usual range, assessments, notable metrics, the stuck flag and display units. Standard library only, so other tools (like a future weekly-review skill) can reuse them.
  - `validate.py`: the validator. Errors fail it; warnings, gaps and skipped days are reported. `--json` is for programs.
  - `setup.py`: `dotlife setup`: the plain questions everyone answers first (what to track, apps, their own words, show sensitive), `--answers` for agents to change them, and `--finish`, which deletes `sample/` once there is data; all write `config.toml` and the start of `sources.md` with the same code.
  - `terminal.py`: the questionnaire's arrow-key menus (standard library: `termios` or `msvcrt`), with numbered prompts when input isn't a terminal. Colour honours `NO_COLOR`.
  - `fresh.py`: `dotlife fresh`, which runs the person's source scripts listed in `config.toml`, merges what they staged, then validates. It records when each step last finished in `.dotlife/good_runs.json`, so a failed step can say how old its rows are.
  - `staging.py`: what source scripts import: `from_env()`, `Staging.wants` and `Staging.write`, which stage rows in `data/sources/<source>/`. Also the merge that builds each data file from them, by the ranking in `[sources]`.
  - `cli.py` and `__main__.py`: the `dotlife` command.
  - `dashboard/`: the Streamlit app (`make dashboard`). Use the `developing-with-streamlit` skill when changing it, and keep logic out of the page scripts:
    - `app.py`: entry point, sidebar (period, period picker, "Show sensitive", sample notice) and `st.navigation`.
    - `app_pages/`: Overview, Trends, Reflections, Data health. Plain scripts that only lay things out.
    - `data.py`: cached loading and validation, reloaded when a data file changes, and the sidebar selection.
    - `cards.py`: what each card shows (value, change, chip, usual range, notes), with no Streamlit, so it is testable.
    - `display.py`: number formatting and the areas cards belong to. `charts.py`: Altair charts built from polars frames.
    - The design reference is the mockup in `dev/PLAN.md` (M3). The theme is in `.streamlit/config.toml`, which also turns off usage statistics and keeps the server on this computer only.
- `.agents/skills/`: the `setup`, `fetch` and `maintain` skills (`.claude/skills` links here). Write them for any agent: name capabilities ("a health connector"), not one vendor's tools.
- `docs/sources/`: one guide per data source. People follow them, and the skills read them, so keep them accurate for both.
- `tests/`: unittest tests (`make test`). Docstring examples run as tests too.

## Project rules

- **Missing data stays missing.** Code never estimates, interpolates or invents a value. It reports gaps.
- **Scripts over AI calls.** Anything that can be scripted is a script.
- **Settings in `config.toml`**, not in code or prose.
- **Weeks** run Monday to Sunday in the user's local time zone (`zoneinfo`). **Sleep** counts toward the wake date. Clock-time maths uses minutes after 18:00.
- **No real personal data** in this repo: not in sample data, examples, tests, screenshots or docs. Everything is made up.
- **Keep it small.** Prefer fewer files and plain code over abstractions.

## Setup and conventions

- Python 3.11+. Everything in `dotlife/` except `dashboard/` uses only the standard library. The dashboard's dependencies are managed with uv in `pyproject.toml` (`uv add <pkg>`).
- `make install` sets up the environment. `make` lists the other commands.
- `make check` runs what CI runs (lint, formatting and pyright type checks) without changing files. GitHub Actions also runs `make test` on Python 3.11 to 3.14, on Ubuntu (`.github/workflows/ci.yml`).
- `make format` runs ruff and pymarkdown. Ruff enforces the docstring and import rules (see `pyproject.toml`). Write Markdown with blank lines around headings and lists, one paragraph per line.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/). Keep them small, with formatting changes in their own commit.

## Releases

Cut a release at the end of every milestone in the roadmap, so each one is something people can download.

Versions follow [Semantic Versioning](https://semver.org) and are worked out from commit messages by [git-cliff](https://git-cliff.org) (config in `cliff.toml`):

- dotlife is in alpha. While the latest tag is a pre-release (`v0.1.0-alpha.1`), each release bumps the pre-release number. Moving to beta or to a stable version is chosen by hand.
- After that, before 1.0, `feat` commits and breaking changes bump the minor version, and everything else bumps the patch version. Version 1.0.0 is chosen by hand.
- `make release` sets the version in `pyproject.toml` (in Python's format, e.g. `0.1.0a1`) and rewrites `CHANGELOG.md`. Override it with `BUMP=major|minor|patch`, or with an exact `VERSION=v0.1.0-beta.1`.
- It doesn't commit. Review the changes, commit them as `chore(release): vX.Y.Z` and push to `main`.
- Once CI passes on `main`, `.github/workflows/release.yml` tags that commit and publishes a GitHub release, with the changelog section as its notes. It runs only when no release exists yet for the version in `pyproject.toml`, so ordinary pushes publish nothing. Pre-releases are marked as such.
- Each release page offers the source code as zip and tar.gz downloads.
- The changelog is for people who use dotlife. It lists `feat`, `fix`, `perf`, `docs` and `revert` commits only; `chore`, `ci`, `build`, `test`, `refactor` and `style` commits are left out, and so are commits that don't follow Conventional Commits, such as merges. Give a change users notice one of the listed types, and work on dotlife's own tooling or contributor docs another type or the `dev` scope (`docs(dev): ...`).
- Never edit `CHANGELOG.md` by hand or commit changelog fixes: change the commit types or `cliff.toml`, and the next `make release` rewrites it.
- Don't rewrite history below a release tag. If it happens, point the tag at the rewritten commit (`git tag -f vX.Y.Z <commit>`, then `git push --force origin vX.Y.Z`); otherwise git-cliff no longer sees the release and proposes the same version again.

## Python style

### Data and structure

- Classes are dataclasses, `frozen=True` and/or `slots=True` where they fit (category specs are frozen).
- Prefer composition to inheritance.
- Use `@property` for computed attributes. Don't add methods that aren't needed.

### Functions

- Each function does one thing. Return early instead of nesting.
- No mutable default arguments.
- Use `with` for every file or resource.
- Raise errors with messages that say what was wrong and where (file, row, column).
- Use comprehensions and generators, `enumerate()`, f-strings, and `is` for `None`, `True` and `False`.

### Imports

- Absolute only. No wildcard imports.

### Docstrings

Google style.

- Every public function, class and method has one, with `Args:`, `Returns:` and `Raises:`, plus an example for complex functions.
- No module-level (file) docstrings.

### Names

- Descriptive. `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_CASE` for constants.

### Comments

- Only where the code can't say it. No restating the code, no describing the file.
- Keep comments current with the code.

### Characters

- No emoji or emoji-like symbols (such as check marks) in code, docs or output. Tests of multibyte handling are the only exception.

### Performance and size

- Optimal big-O. Use polars (never pandas) in the dashboard, with expressions rather than row loops.
- No code beyond what's needed. Reuse rather than repeat.
- The stdlib-only rule for `dotlife/` (except `dashboard/`) overrides any urge to add a library.
