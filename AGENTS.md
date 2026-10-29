# AGENTS.md

Instructions for AI agents working in a dotlife repo. Claude Code reads this through `CLAUDE.md`.

This repo holds one person's life data in the dotlife format: plain CSV and Markdown files that a dashboard reads. Your job is usually to set up their sources, sync new data into the files, validate them, or answer questions about them. The project is early, so some of the files below don't exist yet.

## Files

- `FORMAT.md`: the data format. It is the source of truth for every file, column, unit and rule. Read it before writing any data file.
- `config.toml`: the person's settings: time zone, which categories are switched on, thresholds, budgets and custom metrics. Change it only when they ask, and say what changed.
- `sources.md`: their setup in plain words: which source provides each category, the priority when two sources overlap, the choices the guides leave to them, and how each source is fetched. `setup` writes it and `maintain` keeps it current. Read it before changing anything.
- `data/`: their data files, in the format. `sync` writes them.
- `scripts/`: their own import scripts, written by `setup` and run by `make fresh`.
- `prompts/`: instructions for steps only an agent can do, one file per step, e.g. `prompts/mood.md` for inferring mood from reflections.
- `inferred/`: what the agent answered for each inferred metric, with a few words of evidence per day. Scripts map it into `data/`.
- `sample/`: made-up demo data (Alice, of Alice and Bob). The dashboard falls back to it when `data/` doesn't exist. Never write the person's data here. `setup` deletes it at the end.
- `docs/sources/`: one guide per data source: how to get the data out and how it maps to the format.
- `dotlife/`: dotlife's own code. Leave it alone during setup and sync (see the last section).

## Skills and commands

- `make setup` (`uv run dotlife setup`): the questionnaire, for people without an agent: what to track, the apps and devices used, a ranking where they overlap, and a review of which source fills what. It writes `config.toml` and the start of `sources.md`.
- `setup` (in `.agents/skills/`): the agent's path. It proposes what to track and where it comes from, from what it knows and what it asks, checks the plan with the person, and records it with `uv run dotlife setup --answers <file>` (`--print-answers` shows the current answers as JSON). Don't edit `track` or `[sources]` in `config.toml` by hand. Then it reads the guides in `docs/sources/`, writes the scripts, lists them for `make fresh`, runs it once and deletes `sample/`.
- `make fresh`: runs every source script in the order `config.toml` lists, then the validator. No agent needed; the person runs it whenever they want fresh data.
- `fetch` (in `.agents/skills/`): does the steps only an agent can do (connector-only sources and AI inference), then runs `make fresh`.
- `maintain` (in `.agents/skills/`): for when `make fresh` fails, or to add a source, change a device or change how something works. It updates the scripts, `config.toml` and `sources.md` together.
- `uv run dotlife validate`: check the files. Fix what it reports at the source or in the import, never by editing values to pass.
- `uv run dotlife dashboard`: open the dashboard.

## Writing a source script

`make fresh` runs `dotlife fresh`, which runs each script listed under `[[fresh.steps]]` in `config.toml`, in order, then the validator. A script must:

- Be listed with a `name` and either `script = "scripts/<name>.py"` (run with dotlife's Python; standard library only) or `command = [...]` for anything else, e.g. a Swift script for Apple Calendar.
- Read the data folder from `DOTLIFE_DATA` and the settings from `DOTLIFE_CONFIG`. It runs in the folder holding `config.toml`.
- Write only its own categories' files in the data folder, following `FORMAT.md` and the source's guide in `docs/sources/`. Running it twice must give the same files: re-fetch a recent window and replace those rows rather than appending.
- Keep secrets (tokens, passwords) out of the repo: read them from the environment or the system keychain, and say where in `sources.md`.
- Print a line or two about what it did, and exit 0 when it finished. On failure, print what went wrong in plain words and exit with any other code. A source that needs a manual step, like a new Apple Health export, finishes with a note when there's nothing new.

A step only an AI agent can do (a source reachable only through a connector, or AI inference) is listed with `agent = "prompts/<name>.md"`, the instructions the agent follows. `make fresh` lists it as left for your agent and doesn't run it; the `fetch` skill does it, then runs `make fresh`. The agent saves what it fetched or inferred as a file, exactly as it got it, and a script step maps that file into the data files: the agent never edits data files itself.

`dotlife fresh --only <name>` runs one step. The last run's output is in `.dotlife/fresh.log`.

## Data rules

- **Missing data stays missing.** Never estimate, interpolate, forward-fill or invent a value. Leave the cell empty and report the gap. The one exception is inference the person opted into, on the terms in `FORMAT.md` ("Inferred values"): labelled `inferred-<input>`, never over a recorded value, and empty without evidence.
- **Scripts over AI.** Every source gets a script that `make fresh` can run without an agent. A connector needs an agent, so use one only for a one-off backfill a script can't do, transcribe its values exactly, and note it in `sources.md`.
- **One source per metric.** When two sources report the same metric, keep the one `sources.md` ranks higher. For weight, a smart-scale reading wins on any day it has one.
- **Dates are local.** Weeks run Monday to Sunday in the time zone in `config.toml`. A night's sleep counts toward the date the person woke up.
- **Record only new readings.** If a source keeps repeating an old value (e.g. VO2 max that only updates after an outdoor run), don't write it again as a new reading.
- **Switched-off categories are off.** Don't fetch, write or discuss data for a category that is disabled in `config.toml`. Ask before switching on a sensitive category (reflections, cycle, medication, symptoms, glucose, finances, social, travel).

## Privacy

- This data is personal. Keep it in this repo. Don't send it anywhere `sources.md` doesn't already name, and don't put it in issues, pull requests or messages to dotlife.
- Quote reflections sparingly and only when asked.

## Changing dotlife's code

If you are changing dotlife itself (`dotlife/`, `tests/`, `FORMAT.md`, skills or docs), follow `CONTRIBUTING.md`.
