# Inference

Inference fills a metric from data you already have instead of from a device or an app: how often you dined out, counted from bank transactions, or your mood, read from your reflections. It's opt-in per metric, and it follows the rules in [FORMAT.md, "Inferred values"](../../FORMAT.md#inferred-values): labelled `inferred-<input>`, never over a recorded value, written once, and empty when the input says nothing.

There are two kinds, and the first is always preferred:

- **By rule.** A script decides, so the answer is the same every time and needs no AI. Use it whenever the input has a field that settles the question, like a transaction's category.
- **By AI.** Your agent reads text and answers a question about it. Use it only when the answer needs reading, like mood in a reflection.

## What it fills

Examples. Any metric in the format can be inferred if you have an input that answers it; these are the common ones.

| dotlife column | Inferred from | Kind | Notes |
| --- | --- | --- | --- |
| A custom metric, e.g. `dining_out` (summary `sum`) | `finances.csv` | Rule | Count of transactions whose `category` is the one you use for eating out, or whose merchant category code is a restaurant code (see below). |
| `mood.mood`, `mood.energy`, `mood.stress` | `reflections/` | AI | 1 to 5, the format's scale. Only from what the day's entries say. |
| `social.social_h` | `reflections/` | AI | Only when an entry states a time or a duration. "Dinner with Bob" alone has no hours, so it stays empty. |
| `habits.times` for a habit, e.g. `walk` | `reflections/` | AI | Only when an entry says it happened. |

Dining out has no column of its own, so it's a [custom metric](../../FORMAT.md#custom-metrics), e.g. `[custom.dining_out]` with `summary = "sum"` and `unit = "times"`.

## Getting the data out

### By rule

Write a script that reads the input file in the data folder (`from_env().data_dir`), applies the rule, and stages the metric's rows as the source `inferred-<input>`, e.g. `staging.write("inferred-finances", "dining_out", rows)`. List it in `config.toml` after the step that fills its input, so it reads fresh data:

```toml
[[fresh.steps]]
name = "dining-out"
script = "scripts/dining_out.py"
```

For dining out:

- If your bank export has a category you assign (e.g. `restaurants`), count those rows per day. Count spending only (`amount` below 0).
- If it has merchant category codes, restaurants are 5812 (eating places and restaurants) and 5814 (fast food restaurants); 5813 is bars ([Eesti Pank's list of merchant category codes](https://www.eestipank.ee/en/list-merchant-category-codes)). Which code a business gets is up to its card processor, so check a few of your own transactions before trusting the rule.
- Refunds and split bills show up as extra transactions. Decide with the person how to count them, and write the rule in `sources.md`.

### By AI

The agent's part runs in the `fetch` skill, never in `make fresh`. It takes three files in the repo:

1. **Instructions**, e.g. `prompts/mood.md`: what it fills, what to read, the question with its scale, what counts as evidence, and where to save the answers. Write them with the person and keep them short. Anchor every point of the scale, so different models and runs split days the same way. For mood:

   ```markdown
   Fills: mood.mood (the mood category), from reflections.

   Read: data/reflections/<year>.txt, one finished day at a time.

   Question: rate the mood that day's entries describe:
   1 very low, 2 low, 3 neutral or mixed, 4 good, 5 very good.
   Use only what is written that day. If the entries say nothing about mood,
   give no rating.

   Save: inferred/mood.csv, columns date, mood, evidence.
   ```

2. **Answers**, e.g. `inferred/mood.csv`: the agent writes one row per day it was asked about, with `date`, the value, and `evidence`, a few words on why (not a copy of the text). A day the input says nothing about gets a row too, with the value empty, so it isn't asked again. It is the record of what the AI said, so keep it in the repo.
3. **A script**, e.g. `scripts/mood_inferred.py`, that reads the answers file (paths like `inferred/mood.csv` are relative to the folder holding `config.toml`, where scripts run) and stages every answer with a value as the source `inferred-reflections`: `staging.write("inferred-reflections", "mood", rows)`. It skips empty values and values outside the format's limits.

List the agent's part and the script in `config.toml`, in that order:

```toml
[[fresh.steps]]
name = "mood-from-reflections"
agent = "prompts/mood.md"

[[fresh.steps]]
name = "mood-inferred"
script = "scripts/mood_inferred.py"
```

`make fresh` runs the script and names the agent step as one for your agent's fetch skill; it always does, whether or not there are days left to answer. The `fetch` skill does the agent step, then runs `make fresh`. The agent only answers finished days (before today) with input that are neither in the answers file nor recorded by another source, and only writes to `inferred/`, never to the data files.

## Mapping to the format

- **Source.** `inferred-<input>`, naming the file or folder it came from: `inferred-reflections`, `inferred-finances`. The validator rejects a bare `inferred`.
- **Dates.** A value belongs to the day of its input: a reflection's local date, a transaction's `date`.
- **Recorded wins.** List the inferred source last in `[sources]`, e.g. `mood = ["obsidian-daily-notes", "inferred-reflections"]`. `make fresh` then uses an inferred row only on days no recorded source has, and a recorded value that arrives later replaces it.
- **Written once.** A day already inferred is left as it is, so changing models or instructions doesn't rewrite the past. To redo a range, the person asks for it, and `sources.md` notes when and why.
- **Empty without evidence.** A day the input doesn't speak to gets no value in the data file, not a middle value. Its row in the answers file has the value empty, which records that it was asked.
- **Same scale.** Use the format's scale (mood 1 to 5) in the instructions, so inferred and recorded values can share a chart.

## Watch out for

- **Privacy.** AI inference sends the input to your agent's model provider. Reflections and finances are sensitive; choose this knowingly, per metric. A source's own terms can forbid it: [Oura's API agreement](oura.md) limits passing Oura data to AI models, so never use AI inference on data from Oura.
- **What you wrote isn't how you felt.** Mood read from reflections reflects what you chose to write. Days you didn't write are empty, and busy days often go unwritten.
- **Drift.** The same instructions can get different answers from a different model. Writing each day once keeps the past stable; the dashboard's "inferred" note keeps it visible.
- **Rule edge cases.** Merchant codes vary between card processors, and bank categories change when you recategorise. Check the counts against a month you remember.

## Not in the format

- The `evidence` column stays in `inferred/`; the data files hold only the value.
- A confidence score from the AI: dotlife doesn't use one. Leave unclear days empty instead.

## Sources

- [Eesti Pank: List of merchant category codes](https://www.eestipank.ee/en/list-merchant-category-codes)

Checked 2026-10-29.
