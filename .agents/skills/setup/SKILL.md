---
name: setup
description: Set up a dotlife repo for its owner. Work out what they track and where each kind of data comes from, record the plan with `dotlife setup --answers`, then write a script per source so `make fresh` fills `data/` from then on. Use when the person asks to set up dotlife, connect their apps or devices, or start tracking; for changes to a working setup, use the maintain skill instead.
---

# Set up dotlife

At the end of this skill the person has:

- `config.toml` with `track`, `[sources]` and their settings, written by `dotlife setup --answers`.
- `sources.md` saying, in plain words, where each kind of data comes from and every choice the guides left to them.
- One script per source in `scripts/`, listed under `[[fresh.steps]]` in `config.toml`.
- A first `make fresh` that finishes, with the validator's findings explained to them.
- No `sample/` folder.

Read `AGENTS.md`, `FORMAT.md` and `docs/sources/README.md` before you start. Their rules hold throughout: missing data stays missing, scripts over AI, sensitive categories only with consent, and the person's data stays in this repo.

## 1. Check where things stand

Run `uv run dotlife setup --print-answers`. If `track` is already filled in, the repo has been set up before. Ask whether they want to start over or change one thing; for one thing, use the maintain skill.

## 2. Find out what they use

Start from what you already know about the person: their memory with you, this conversation, files they point you to. Then ask, in one round, only what you can't assume:

- Phone, watch, ring, smart scale and the apps that go with them.
- Where they write things down: a journal app, daily notes, a calendar for time use.
- Anything else they want to see, e.g. reading, habits, a custom number like guitar practice.
- Their time zone, if this computer's may be wrong. Before the first setup, `--print-answers` shows this computer's zone, not the one in the template's `config.toml`.

Always ask before tracking a sensitive category: reflections, cycle, medication, symptoms, glucose, finances, social, travel. Never assume one in.

## 3. Propose the plan

Show a table of category, source (best first) and the guide it follows, then what nothing covers. Build it from these rules:

- Sources are the slugs in `docs/sources/README.md`'s guides (`apple-health`, `oura`, `jrnl`, `open-meteo` and so on), `manual` for entries made by hand, and `inferred-reflections` or `inferred-finances` for inference (`docs/sources/inference.md`). A source without a guide gets a new lowercase-hyphenated slug; say that it has no guide yet and that you will work out its mapping from its own documentation.
- Order matters: for each date, `make fresh` keeps the rows of the first listed source that has data that day. Put the most complete source first. For weight, a smart scale goes first when it is a source of its own; when it writes into another source (e.g. through Apple Health), that source's script ranks it, following the guide's choices. Inferred sources always go last.
- Weather comes from `open-meteo` with no account, for a home location rounded to two decimals.
- Leave out categories with no source rather than listing `manual` for them, unless they will really enter values by hand.
- Also settle the details: week or month, kg or lb, mmol/L or mg/dL, and for finances the home currency and monthly budgets.

Wait for a clear yes. Change the plan as often as they like.

## 4. Record the plan

Write the answers as JSON to a temporary file outside the repo, in the format `--print-answers` shows, then run:

```sh
uv run dotlife setup --answers <file>
```

It checks the answers and writes `config.toml` and the top of `sources.md`. Fix whatever it rejects and run it again. Delete the temporary file. Never edit `track` or `[sources]` in `config.toml` by hand.

## 5. Settle each source's choices

For each source in turn, read its guide in `docs/sources/` from start to end. Most guides have a "Choices to make" section; others leave choices in their mapping notes. Ask the person about each, with the guide's usual answer as the default. Then add a section to `sources.md`, below the setup markers, headed with the source's name (`sources.example.md` shows finished ones):

- How the data gets out, and what the person has to do each time, e.g. "Export from the Health app into `inbox/export.zip`".
- Every choice and its answer, including any ranking inside the source (e.g. watch over phone) that `[sources]` can't show.
- Where secrets are kept (environment variable or keychain item), never the secret itself.
- Anything that differs from the guide, and why.

A source's settings that a script needs (a file path, a location) go in `config.toml` in a table named after the source, e.g. `[apple-health]`. Weather's location is already in `[weather]`.

If a device only fills the days the main one missed (a phone on days without the watch), list its `source` value in `fallback_sources` under `[activity]`, so those part-day rows stay out of averages. Never when it is their only device.

If the source needs an export or a token the person doesn't have yet, walk them through getting it now, following the guide.

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
- On failure, print what went wrong and what to do in plain words, and return 1. A source with a manual step that finds nothing new says so and returns 0.
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

- Delete `sample/`: the dashboard now reads `data/`. It stays in git history.
- Tell them how to refresh from now on: `make fresh`, plus any manual step a source needs (e.g. a new Apple Health export into `inbox/` first), and that the fetch skill does agent steps.
- Suggest `make dashboard` to see it.
- Don't commit. Show what changed (`git status`) and let them commit it.
