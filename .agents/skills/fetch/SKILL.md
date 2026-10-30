---
name: fetch
description: Do the dotlife steps only an agent can do, then run `make fresh`. These are the `agent = "prompts/<name>.md"` steps in `config.toml`, for AI inference (e.g. mood read from reflections) and for sources reachable only through a connector. Use when the person asks for fresh data and such steps exist, or when `make fresh` says steps are left for their agent.
---

# Fetch with an agent

`make fresh` runs every script and names the `agent` steps as ones for your agent's fetch skill; it names them on every run, whether or not anything is left to do. This skill does those steps, in the order `config.toml` lists them, then runs `make fresh` so their scripts stage what you saved. You never write the data files: you save what you inferred or fetched as a file, and a script step after yours stages it.

Read `AGENTS.md` and the person's `sources.md` first. Their rules hold: missing data stays missing, an inferred value never passes for a recorded one, and the data goes nowhere `sources.md` doesn't name.

## 1. Find the steps

Run `make fresh` first, so the data files include everything staged since the last run (a reflection or a rating the person just added by hand). Then list the `[[fresh.steps]]` with an `agent` key in `config.toml`. For each, read its instructions file (e.g. `prompts/mood.md`) and the source's section in `sources.md`. Skip a step whose category is switched off (not in `track`), and say so.

The instructions must say what they fill (category and column), what to read, what to answer or fetch, and where to save it. If any of that is missing or unclear, stop and ask the person (or use the maintain skill to fix the instructions); don't guess.

## 2. Inference steps

The rules are in `docs/sources/inference.md` and FORMAT.md's "Inferred values". In short:

1. **Which days.** Finished days (before today, in the time zone in `config.toml`) that have input (e.g. a date with reflections in `data/reflections/`), minus days already in the answers file (e.g. `inferred/mood.csv`: each day is answered once), minus days whose metric already has a recorded value in the data file from a source that isn't `inferred-*` (a recorded value always wins, so asking would only cost). Today is left for a later run: a day answered once is never answered again, so an answer from half a day's entries would stay. With nothing left, the step is done.
2. **Privacy check.** The input goes to your model provider. Go on only if `sources.md` says the person chose this inference. Never infer from data whose terms forbid it; Oura's API agreement does (`docs/sources/oura.md`).
3. **Answer each day from that day's input only**, following the instructions exactly: the format's scale, and nothing from other days, other files or what you know about the person.
   - With evidence: a row with `date`, the value, and `evidence`, a few of your own words on why. Never copy the input's text into `evidence`.
   - Without evidence: a row with `date`, the value left empty, and `evidence` saying the input doesn't speak to it. That records that the day was asked, so it isn't asked again.
4. **Save as you go.** Add the new rows to the answers file, keeping it sorted by date, after every batch of days, so an interruption keeps what was done. Never change or remove an existing row. To redo a range, the person must ask; then replace those rows and note the date and reason in `sources.md`.

## 3. Connector steps

For a source only a connector reaches (an app with no API or export a script could use):

1. Check that this agent has the connector the instructions name. If not, tell the person and skip the step; don't substitute another one.
2. Fetch exactly what the instructions say, for the window they give (e.g. the last 7 days).
3. Save the answer exactly as the connector returned it, under the folder the instructions name, e.g. `inbox/<step>/` (git ignores `inbox/`), in a file named after the window. Don't convert units, fix values or fill gaps: the script does the mapping, following the source's guide.

## 4. Run and report

Run `make fresh`. The script after each agent step stages what you saved; check its lines and the validator's.

Tell the person in a few lines: per step, how many days were answered (with a value, and without evidence) or what was fetched, anything skipped and why, and the validator's result. For inference, remind them once that inferred days are marked as inferred in the dashboard.

Don't commit. Show `git status` (the answers file in `inferred/` and the staged rows changed) and let them commit it.
