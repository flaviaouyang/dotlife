---
name: setup
description: Set up a dotlife repo for its owner. Work out what they track and where each kind of data comes from, record the plan with `dotlife setup --answers`, then write a script per source so `make fresh` fills `data/` from then on. Use when the person asks to set up dotlife, connect their apps or devices, or start tracking; for changes to a working setup, use the maintain skill instead.
---

# Set up dotlife

At the end of this skill the person has:

- `config.toml` with `track`, `[sources]` and their settings, from `dotlife setup`.
- `sources.md` saying, in plain words, where each kind of data comes from and every choice the guides left to them.
- One script per source in `scripts/`, listed under `[[fresh.steps]]` in `config.toml`.
- A first `make fresh` that finishes, with the validator's findings explained to them.
- No `sample/` folder.

Read `AGENTS.md`, `FORMAT.md` and `docs/sources/README.md` before you start. Their rules hold throughout: missing data stays missing, scripts over AI, the most automatic route, sensitive categories only with consent, and the person's data stays in this repo.

## 1. Get their answers

The person answers a fixed set of plain questions first, in `dotlife setup`. You don't ask them again what to track, which apps they use or what "sensitive" means; the questions show the supported apps and what each fills.

Run `uv run dotlife setup --print-answers`. If `track` is empty, setup hasn't been done: tell them to run `make setup` themselves (in this session: `! make setup`), since it is a menu you can't drive, and wait. Don't answer the questions for them. If `track` is filled in, the repo was set up before: ask whether they want to start over or change one thing; for one thing, use the maintain skill.

Then read `sources.md`: the setup block lists the sources, which source wins, and under "In your own words" anything they said that no guide covers.

## 2. Understand what they said

From their answers, your memory of them and the guides, work out what's left:

- **Their own words.** Each app, device or file they named: does a guide cover it (`docs/sources/README.md`)? If not, find out how its data can be read, from its own documentation, and say there is no guide yet.
- **Categories with no source** (listed as "By hand" in the plan). Ask only about these, once: is there an app or file that holds it? Don't list the categories again.
- **Details only they know**, e.g. which jrnl journal, which calendar. Look up what you can (config files, `jrnl --list`) before asking.

Ask in one round, in plain words, with examples. Never make them name categories or products from memory.

## 3. Check the plan

Show the table `dotlife setup` assumed (category, source best first, guide), with your changes from step 2 marked, and what nothing covers. Rules for changing it:

- Sources are the slugs in `docs/sources/README.md`'s guides (`apple-health`, `oura`, `jrnl`, `open-meteo` and so on), `manual` for entries made by hand, and `inferred-reflections` or `inferred-finances` for inference (`docs/sources/inference.md`). A source without a guide gets a new lowercase-hyphenated slug.
- Order matters: for each date, `make fresh` keeps the rows of the first listed source that has data that day. Put the most complete source first. Inferred sources always go last, after `manual`.
- A rule you can write as a script (a tag such as `@learn`, a regular pattern) is a script. Only reading free text needs an `agent` step.
- Leave out categories with no source rather than listing `manual` for them, unless they will really enter values by hand.

Wait for a clear yes.

## 4. Record changes

If the plan changed, write only the changed answers as JSON to a temporary file outside the repo, in the format `--print-answers` shows (`sources` replaces the whole table, so send all of it), then run:

```sh
uv run dotlife setup --answers <file>
```

Fix whatever it rejects, then delete the file. Never edit `track` or `[sources]` in `config.toml` by hand. Their dashboard choice (`show_sensitive`) is theirs from the questions; change it only if they ask.

## 5. Settle each source's choices

For each source in turn, read its guide in `docs/sources/` from start to end. Most guides have a "Choices to make" section; others leave choices in their mapping notes. Ask the person about each, with the guide's usual answer as the default. Then add a section to `sources.md`, below the setup markers, headed with the source's name (`sources.example.md` shows finished ones):

- How the data gets out, and what the person has to do each time, e.g. "Export from the Health app into `inbox/export.zip`".
- Every choice and its answer, including any ranking inside the source (e.g. watch over phone) that `[sources]` can't show.
- Where secrets are kept (environment variable or keychain item), never the secret itself.
- Anything that differs from the guide, and why.

A source's settings that a script needs (a file path, a location) go in `config.toml` in a table named after the source, e.g. `[apple-health]`. Weather's location is already in `[weather]`.

If a device only fills the days the main one missed (a phone on days without the watch), list its `source` value in `fallback_sources` under `[activity]`, so those part-day rows stay out of averages. Never when it is their only device.

Pick the route as `docs/sources/README.md` ("Choosing a route") says: the most automatic one that can work for them. A step they repeat before every refresh is the last resort; a one-time step (signing in, installing an app) is fine. If the source needs an export or a token the person doesn't have yet, walk them through getting it now, following the guide.

## 6. Write the scripts

One script per source, `scripts/<source>.py`, filling every category the source has in `[sources]`. Shape:

```python
import sys

from dotlife.staging import from_env

SOURCE = "apple-health"


def main() -> int:
    """Stage this source's rows for every category it fills.

    Returns:
        0 when finished, 1 with a message when something went wrong.
    """
    staging = from_env()
    # Read the source, then for each category it fills:
    if staging.wants(SOURCE, "activity"):
        count = staging.write(SOURCE, "activity", activity_rows)
        print(f"activity: {count} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- Use only the standard library and `dotlife.staging` (see "Writing a source script" in `AGENTS.md`). Settings are in `staging.config`, the time zone in `staging.timezone`.
- Stage rows with `staging.write`; never write `data/` or `sample/` yourself. `staging.wants` is False for categories that are switched off or not from this source, so the script never reads what it shouldn't.
- Follow the guide's mapping exactly: units, local dates, the wake date for sleep, one source per day, empty cells for missing values, a row only when a reading is new.
- Work out lengths of time from the times as parsed, with their offsets, never from local wall-clock times: those are wrong across a clock change. Convert to the local zone only for dates and written timestamps.
- Round sums to a sensible precision (whole steps, minutes and metres) so floats don't leave long tails.
- A source read in full (an export) stages every row each run. An API re-fetches a recent window and passes `window=(first, last)`; on the first run, it fetches from the start date the person chose.
- A large file is streamed, never loaded whole.
- A source waiting on the person (no export yet, or the same one as last time) prints what to do and returns 0. When something must be fixed or done first (an unreadable file, an unknown unit, a missing or expired sign-in, a permission not granted), print what in plain words and return 1. Never stage a placeholder or an empty file to look finished, and never return 0 when the source could not be read.
- Never change the computer's privacy permissions (no `tccutil`), and never build, sign or install an app to get a permission prompt. Test a script that depends on a permission only in the person's own terminal; your shell has a different identity, so success there proves nothing. If one try there fails, don't try variants: use the next route down in the guide and note why in `sources.md`.
- Write it plainly, with a docstring per function, so the person or the maintain skill can follow it later.

Add each script to the end of `config.toml`, sources first and any inference rule after the source it reads:

```toml
[[fresh.steps]]
name = "apple-health"
script = "scripts/apple_health.py"
```

A source a script can't reach (a connector only an agent can use) gets an `agent = "prompts/<name>.md"` step instead; the fetch skill runs those.

## 7. Run it and check

Run `make fresh`. Read the whole output, and `.dotlife/fresh.log` if it is long.

- A step that fails: fix the script and run `uv run dotlife fresh --only <name>` until it finishes.
- Validator errors: fix them in the script, never by editing values. Rerun.
- Warnings and gaps: explain each to the person in a sentence. Most are real (a day the watch was off, a run of 62,000 steps); change a plausible bound in `config.toml` only when they say the value is right.
- Then pick one recent day and ask them to compare a few values with what the source's own app shows, e.g. steps and time asleep. Investigate any difference before going on.

## 8. Finish

- Tell them how to refresh from now on: `make fresh`, plus any step a source needs each time (e.g. a new export into `inbox/`), and that the fetch skill does agent steps.
- Suggest `make dashboard` to see it.
- Don't commit. Show what changed (`git status`) and let them commit it.
- Last, clean up: run `uv run dotlife setup --finish`. It deletes `sample/` (it stays in git history) and refuses until `data/` has data; if it refuses, finish step 7 first. Don't skip it or leave `sample/` for later.
