---
name: maintain
description: Keep a working dotlife setup working. Use when `make fresh` fails or reports problems, or when the person wants to add a source, stop one, change a device, switch a category on or off, or change how a source is read. Updates the scripts, `config.toml` and `sources.md` together. For a repo that was never set up, use the setup skill instead.
---

# Maintain dotlife

Every change keeps three things in step: the scripts in `scripts/`, `config.toml` (`track`, `[sources]`, `[[fresh.steps]]` and each source's own table), and `sources.md`, which says in plain words what the other two do. A change to one without the others is how a setup rots.

Before anything, read `AGENTS.md`, the person's `sources.md`, and `uv run dotlife setup --print-answers`. `sources.example.md` shows what a finished `sources.md` looks like. The rules in `AGENTS.md` hold: missing data stays missing, scripts over AI, sensitive categories only with consent, and the data stays in this repo.

Find which case this is, follow it, then finish with "Check and hand back".

## `make fresh` failed or warned

Read the whole output, or `.dotlife/fresh.log` for the last run. Then, by what it says:

- **A step failed** (`failed (exit code N); its rows are from <time>`). The rows from that good run are still in the data, so say so to the person: those days are not fresh. Read the step's own lines just above, then its script.
  - A missing or old export (Apple Health, a calendar file): tell the person how to export again, from `sources.md`. Nothing is broken. If the script failed rather than finishing with a note, change it to return 0 with that note (see "Writing a source script" in `AGENTS.md`).
  - An expired or revoked token: walk them through signing in again, following the source's guide. Never put the token in the repo.
  - The source changed (a renamed field, a new unit, an error the script doesn't know): check the source's guide and the source's own documentation, fix the script, and note the change under the source in `sources.md`. If the guide itself is now wrong, say so to the person: they can report it to dotlife, without any of their data.
  - A permission or other thing that depends on the launching app (a calendar, a keychain): test only in the person's own terminal, by asking them to run `make fresh`; your shell has a different identity, and your success there says nothing about theirs. Don't claim a fix you couldn't test there. Never reset or change their privacy permissions, and never build, sign or install an app to get a prompt. After one failed fix, stop and take the next route down in the guide (`docs/sources/README.md`, "Choosing a route"), then say in `sources.md` why.
  - Don't leave a step that fails on every run: switch it to another route or remove it, and record that in `sources.md`.
  - Then run `uv run dotlife fresh --only <name>` until the step finishes.
- **Validator errors.** Fix them in the script that staged the rows, never by editing values. The staged rows are in `data/sources/<source>/`, so the row tells you which script it came from.
- **Warnings and gaps.** Explain each in a sentence. Most are real (a day without the watch, a long run). Change a plausible bound in `config.toml` only when the person says the value is right.
- **Merge lines.**
  - `left out <source>, because [sources] doesn't list it`: a script stages a category it shouldn't, or the plan is missing a source. Ask which, then fix the script or the plan (see "Change the plan").
  - `left out <source>, because it is switched off`: the category was switched off; the script should check `staging.wants` before staging it.
  - `<column> from <source> left out on N days`: a lower source had a value the winning source lacked those days. Tell the person; they may want to change the ranking.

## Change the plan

For adding or stopping a source, reordering sources, or switching a category on or off. Never edit `track` or `[sources]` by hand:

1. Save `uv run dotlife setup --print-answers` to a temporary file outside the repo.
2. Change it with the person: what to track, and each category's sources, best first. Always ask before switching on a sensitive category (reflections, cycle, medication, symptoms, glucose, finances, social, travel). Inferred sources stay last.
3. Run `uv run dotlife setup --answers <file>`, fix what it rejects, then delete the file.

Then, for each kind of change:

- **Add a source.** Choose its most automatic route (`docs/sources/README.md`, "Choosing a route"). As in the setup skill, steps 5 and 6: read its guide, settle its choices with the person, add its section to `sources.md`, write `scripts/<source>.py` with `dotlife.staging`, and add its `[[fresh.steps]]` entry. Existing scripts stay as they are: `make fresh` merges by the new ranking.
- **Add inference** (`inferred-<input>`). First decide whether it is a rule or reading text: a tag or pattern (such as `@learn` in reflections) is a script, with no agent step and no consent to send text to a model. Reading free text is an agent step. Follow `docs/sources/inference.md`: a rule is a script; reading text is an agent step `prompts/<metric>.md` that saves answers to `inferred/<metric>.csv`, followed by a script `scripts/<metric>_inferred.py` that stages them. Write the instructions with the person, record their consent to sending the input to their agent's model provider in `sources.md`, and keep the inferred source last in `[sources]`.
- **Add hand entries** (`manual`). No script or step: follow `docs/sources/manual.md`. Values the person gives you go into `data/sources/manual/<file>` exactly as given; never fill in days they didn't give.
- **Change a device**, e.g. from a Fitbit to an Apple Watch. Add the new source first in `[sources]` and keep the old one after it, so past days keep its rows. Remove the old source's step from `[[fresh.steps]]`, so nothing fetches it any more, but keep its staged rows. If one device only fills days the other missed (a phone without the watch), list it in `fallback_sources` under `[activity]`.
- **Stop a source.** Ask whether to keep its past rows. To keep them, remove only its `[[fresh.steps]]` entry and say in `sources.md` that it stopped and when. To drop them, also take it out of `[sources]`: where other sources remain, its rows leave the data files on the next run. Where it was a category's only source, the merge no longer touches that data file, so delete the file too if they want those rows gone. Delete `data/sources/<source>/` only when they confirm, since an API that has forgotten the old days can't rebuild it.
- **Switch a category off.** Leave its staged rows and its data file alone unless they ask to delete them; a switched-off category is hidden and skipped, not erased.
- **Switch a category on.** Check that a source in `[sources]` fills it, and that its script stages it; `staging.wants` turns true for it now. A sensitive category follows their `show_sensitive` choice from `dotlife setup`; tell them if it will be hidden.

## Averages look wrong on days without the main device

When the person has a watch and a phone and the phone's part-day counts pull averages down, list the phone's `source` value (e.g. `iphone`) in `fallback_sources` under `[activity]`, and say so under the source in `sources.md`. Those days stay in the files but out of averages. Never do it when the phone is their only device.

## Change how a source is read

A choice in `sources.md` (the sleep gap, which app wins for weight, a calendar's categories) or a setting in its `config.toml` table:

1. Change the choice in `sources.md` and the setting in `config.toml`.
2. Change the script to match, if the choice lives in code.
3. Tell the person whether past days change too. A source read in full (an export) restages every day on the next run, so past values move to the new rule. A source fetched in a window only changes those days; to redo the past, run its script once with the window from the start, and say so in `sources.md`.

## Check and hand back

1. Run `make fresh`. The step you touched must finish, or, when it waits on the person (a sign-in they haven't done yet), fail with a message that says exactly what to do. The validator must report no new errors.
2. Read `git diff` for `scripts/`, `config.toml` and `sources.md` once more: each change in one has its match in the others.
3. Tell the person in a few lines what changed and what, if anything, they now do differently (e.g. "export again on Sundays").
4. Don't commit. Show `git status` and let them commit it.
