# AGENTS.md

Instructions for AI agents working in a dotlife repo. Claude Code reads this through `CLAUDE.md`.

This repo holds one person's life data in the dotlife format: plain CSV and Markdown files that a dashboard reads. Your job is usually to set up their sources, sync new data into the files, validate them, or answer questions about them. The project is early, so some of the files below don't exist yet.

## Files

- `FORMAT.md`: the data format. It is the source of truth for every file, column, unit and rule. Read it before writing any data file.
- `config.toml`: the person's settings: time zone, which categories are switched on, thresholds, budgets and custom metrics. Change it only when they ask, and say what changed.
- `sources.md`: their setup in plain words: which source provides each category, the priority when two sources overlap, the choices the guides leave to them, and how each source is fetched. `setup` writes it and `maintain` keeps it current. Read it before changing anything.
- `data/`: their data files, in the format. `sync` writes them.
- `scripts/`: their own import scripts, written by `setup-sources` for sources that can be scripted.
- `sample/`: made-up demo data (Alice, of Alice and Bob). The dashboard falls back to it when `data/` doesn't exist. Never write the person's data here. `setup-sources` deletes it at the end of setup.
- `docs/sources/`: one guide per data source: how to get the data out and how it maps to the format.
- `dotlife/`: dotlife's own code. Leave it alone during setup and sync (see the last section).

## Skills and commands

- `uv run dotlife setup`: the questionnaire (what to track, sensitive categories, time zone, devices and apps). It writes `config.toml` and the start of `sources.md`. Deterministic; no agent needed.
- `setup` (in `.agents/skills/`) continues from those answers: reads the guides in `docs/sources/`, writes the scripts, lists them for `make fresh`, runs it once and deletes `sample/`.
- `make fresh`: runs every source script in the order `config.toml` lists, then the validator. No agent needed; the person runs it whenever they want fresh data.
- `fetch` (in `.agents/skills/`): does the steps only an agent can do (connector-only sources and AI inference), then runs `make fresh`.
- `maintain` (in `.agents/skills/`): for when `make fresh` fails, or to add a source, change a device or change how something works. It updates the scripts, `config.toml` and `sources.md` together.
- `uv run dotlife validate`: check the files. Fix what it reports at the source or in the import, never by editing values to pass.
- `uv run dotlife dashboard`: open the dashboard.

## Data rules

- **Missing data stays missing.** Never estimate, interpolate, forward-fill or invent a value. Leave the cell empty and report the gap.
- **Scripts over AI.** If a source can be scripted, write or run a script. Use a connector only where a script can't reach the source, and transcribe its values exactly.
- **One source per metric.** When two sources report the same metric, keep the one `sources.md` ranks higher. For weight, a smart-scale reading wins on any day it has one.
- **Dates are local.** Weeks run Monday to Sunday in the time zone in `config.toml`. A night's sleep counts toward the date the person woke up.
- **Record only new readings.** If a source keeps repeating an old value (e.g. VO2 max that only updates after an outdoor run), don't write it again as a new reading.
- **Switched-off categories are off.** Don't fetch, write or discuss data for a category that is disabled in `config.toml`. Ask before switching on a sensitive category (reflections, cycle, medication, symptoms, glucose, finances, social, travel).

## Privacy

- This data is personal. Keep it in this repo. Don't send it anywhere `sources.md` doesn't already name, and don't put it in issues, pull requests or messages to dotlife.
- Quote reflections sparingly and only when asked.

## Changing dotlife's code

If you are changing dotlife itself (`dotlife/`, `tests/`, `FORMAT.md`, skills or docs), follow `CONTRIBUTING.md`.
