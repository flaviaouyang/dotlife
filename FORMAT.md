# The dotlife data format

Format version 1, set as `format_version` in `config.toml`. This file is the source of truth for every data file dotlife reads. `dotlife validate` checks files against it.

## Files

- All data lives in one folder, `data_dir` in `config.toml` (`data/` by default).
- A data folder can hold its own `config.toml`, which then wins over the repo's. The sample data does this, so it keeps its own time zone.
- Each category has its own file, named in its section below. A category whose file is missing simply doesn't show; nothing else breaks.
- `track` in `config.toml` lists the categories you track, and switches every other one off. Without it, every category with a file shows. `dotlife setup` writes it.
- `enabled = false` in a category's config section switches it off everywhere: the dashboard hides it, the validator skips it, and `make fresh` never fetches it.
- Data files are CSV (UTF-8, comma-separated, with a header row), except reflections, which are plain text.
- Columns can be in any order. The tables below show the suggested order.
- Fields marked *required* must be present on every row. A metric column can be left out of the file entirely when you never have that metric: an activity file with only `date`, `source` and `steps` is valid.

## Values

| Type | Written as | Example |
| --- | --- | --- |
| date | `YYYY-MM-DD`, the local date | `2026-03-08` |
| timestamp | ISO 8601 with a UTC offset | `2026-03-08T07:30-04:00` |
| number | Plain decimal; no thousands separators or units | `8421`, `71.5` |
| text | Any text; quote it if it contains a comma | `"run, easy"` |

- **Missing is empty.** An empty cell means the value wasn't recorded. Never write `0`, `NA` or a guess for a missing value.
- **Units are in column names** (`weight_kg`, `asleep_min`) and are metric. `config.toml` chooses display units, e.g. pounds.
- **Timestamps need their UTC offset**, so they stay unambiguous across daylight saving changes. They can use any offset; dotlife converts them to the time zone in `config.toml`.

## Days, weeks and months

- Dates are local to the time zone in `config.toml`.
- Weeks run Monday to Sunday, and months are calendar months. The dashboard summarises every category over the same period, chosen in `config.toml` or in the dashboard.
- **A night's sleep counts toward the date you woke up**, and a workout toward the date it started.
- **A source's own day.** Some sources total a day that doesn't run from midnight to midnight, such as Oura's activity day from 4 a.m. or a WHOOP cycle from one sleep to the next. Don't split these totals: file each under the date the source gives it, or, for a sleep-to-sleep day, the date you woke up at its start.
- Clock times are averaged as minutes after 18:00, so a bedtime of 00:30 averages with 23:30 to 00:00, not to noon.
- The current week or month is partial. It is compared to date, never projected forward.

## One value per metric

- Each file has at most one row per value of its unique columns (e.g. one row per `date`). The validator reports duplicates.
- `source` says where a row came from (e.g. `watch`, `scale`, `manual`).
- Each source's rows are kept apart, in `sources/<source>/` inside the data folder, with the same file names and columns, e.g. `data/sources/oura/sleep.csv`. The folder is named after the source in `[sources]`; the `source` column inside can be more specific, e.g. `apple-watch` rows in `sources/apple-health/`. `make fresh` builds each data file from them: for each date, it keeps the rows of the source ranked highest in `[sources]` in `config.toml` that has that date. So a smart scale ranked first wins weight on any day it has a reading, and a watch ranked over a phone fills the days the watch was worn. Sleep and workouts are ranked by time rather than by date: a session is kept unless it overlaps one from a higher-ranked source. Transactions and life events keep every source's rows. A value a lower source had, which the kept rows lack that day, is left out, and `make fresh` says so.
- Rows entered by hand go in `sources/manual/`, with `manual` listed in `[sources]`. A data file that no source has rows for is never rebuilt, so it can be kept by hand.
- Record a reading only when the source reports a new one. If a device keeps repeating an old value, don't write it again.

## Inferred values

A value can be worked out from other data instead of recorded: dining out counted from bank transactions, or mood read from reflections. That is inference. It's allowed only on these terms, so an inferred value never passes for a recorded one:

- **Opt in, per metric.** Nothing is inferred unless the person chose it, and `sources.md` says which metrics are inferred and from what.
- **Labelled.** `source` is `inferred-<input>`, e.g. `inferred-reflections` or `inferred-finances`. The validator rejects a bare `inferred`, and the dashboard says how many days of a card or chart were inferred.
- **Last resort.** An inferred value never replaces a recorded one; it only fills a day nothing recorded.
- **Rules before AI.** If a script can decide it (a transaction's category or merchant code), use the script. An AI agent only infers what needs reading, like text.
- **Repeatable.** An AI's instructions live in a file in the repo, e.g. `prompts/mood.md`, so every run asks the same question.
- **Written once.** A day already inferred isn't inferred again unless the person asks, so past values don't drift.
- **No evidence, no value.** When the input says nothing about the metric that day, the cell stays empty.

[docs/sources/inference.md](docs/sources/inference.md) shows how to set it up.

## Limits, warnings and trust

Every number is checked in up to three ways:

1. **Hard limits** mark impossible values, like more than 1,440 minutes in a day or a mood of 6. Where a file has a row per item per day (time use, learning), the hours or minutes across a day's rows can't add up to more than a day either. They are part of the format and are errors.
2. **Plausible bounds** mark unlikely values, like 70,000 steps. They are warnings. Override them in `config.toml`, e.g. `plausible = { steps = [0, 150000] }` under `[activity]`.
3. **Stale and stuck values.** A value that hasn't changed for `stale_after_days` (set per metric in config) is marked stale. A value that stays flat while its related metrics move beyond their usual range is marked stuck. Both are shown with the date of the last real reading and left out of trends. Nothing is corrected or filled in.

## Reflections

Short, text-only notes written through the day, in the plain-text format [jrnl](https://jrnl.sh) uses, so a jrnl file can be read as it is.

- One file a year: `reflections/2026.txt`.
- Each entry starts with its local time in brackets, then its text: `[2026-08-24 22:40] Found a replay attack in section 3. #work`. Lines after it belong to the same entry until the next one.
- A day can have any number of entries. A `*` at the end of an entry's first line stars it, as in jrnl.
- Words starting with `#` or `@` are tags, matched as jrnl does: case is ignored, and a tag can contain `-`, `+`, `*`, `#` and `/`.
- `time_format` and `tag_symbols` in `[reflections]` change the format. The default time format is `%Y-%m-%d %H:%M`; for jrnl's default, use `%Y-%m-%d %I:%M:%S %p`.
- Entries are plain text, not Markdown. Days without one are not gaps.

## Transactions

- One row per transaction. `amount` is signed: negative for money out, positive for money in.
- `currency` is an ISO 4217 code (`EUR`, `CAD`). Amounts in a currency other than `home_currency` in config are flagged, never converted.
- Don't store account numbers. `account` is a name you choose, like `checking`. `description` is optional because it often contains names.

## Custom metrics

Any other daily number can be added without code. Describe it in `config.toml`:

```toml
[custom.guitar]
label = "Guitar practice"
unit = "min"
summary = "sum"          # sum, mean, last, or days
higher_is_better = true
minimum = 0
maximum = 1440
plausible = [0, 180]
```

Its data goes in `guitar.csv` with the columns `date`, `source` and `value`. It gets the same checks, cards and charts as a built-in category.

## Categories

The tables below are generated from `dotlife/categories.py`. *Summary* is how a metric sums up over a week or month. *Better* is the direction the dashboard treats as good, if either.

<!-- categories:start (generated by `make docs`; don't edit by hand) -->

### Activity

Config section `[activity]`. `activity.csv`, one row per day, unique: `date`, expected every day (gaps are reported).

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `steps` | number | steps | no | at least 0 | 0 to 60,000 | average | higher |
| `active_min` | number | min | no | 0 to 1,440 |  | total | higher |
| `sedentary_min` | number | min | no | 0 to 1,440 |  | average | lower |
| `energy_kcal` | number | kcal | no | at least 0 | 0 to 8,000 | average |  |
| `distance_m` | number | m | no | at least 0 | 0 to 100,000 | total | higher |
| `floors` | number | floors | no | at least 0 | 0 to 500 | average | higher |

- `active_min`: The source's own measure of active or exercise time, as it reports it (e.g. Apple's exercise minutes). `sources.md` names the measure.
- `energy_kcal`: Total energy burned in the day: active plus resting.
- Days the watch wasn't worn, or a fallback device filled in, skip averages.

### Workouts

Config section `[workouts]`. `workouts.csv`, one row per session, unique: `start`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `start` | timestamp | | yes | | | | |
| `end` | timestamp | | yes | | | | |
| `type` | text | | yes | | | | |
| `source` | text | | yes | | | | |
| `avg_hr_bpm` | number | bpm | no | at least 0 | 40 to 220 | average |  |
| `distance_m` | number | m | no | at least 0 | 0 to 300,000 | total | higher |
| `energy_kcal` | number | kcal | no | at least 0 | 0 to 5,000 | total |  |

- `energy_kcal`: Energy burned during the session, as the source reports it.
- A session must end after it starts.
- A session is filed under the local date it started.

### Sleep

Config section `[sleep]`. `sleep.csv`, one row per session, unique: `start`, expected every day (gaps are reported).

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `start` | timestamp | | yes | | | | |
| `end` | timestamp | | yes | | | | |
| `source` | text | | yes | | | | |
| `asleep_min` | number | min | no | 0 to 1,440 |  | average | higher |
| `deep_min` | number | min | no | 0 to 1,440 |  | average | higher |
| `rem_min` | number | min | no | 0 to 1,440 |  | average | higher |
| `light_min` | number | min | no | 0 to 1,440 |  | average |  |
| `awake_min` | number | min | no | 0 to 1,440 |  | average | lower |

- A session must end after it starts.
- A sleep session is filed under the local date its sleeper woke up.

### Heart

Config section `[heart]`. `heart.csv`, one row per day, unique: `date`, expected every day (gaps are reported).

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `resting_hr_bpm` | number | bpm | no | at least 0 | 30 to 120 | average | lower |
| `hrv_ms` | number | ms | no | at least 0 | 5 to 250 | average | higher |

- `hrv_ms`: RMSSD. Use SDNN only when the source has no RMSSD, and a value whose method the source doesn't name only when it has neither; say which in `sources.md`.

### Body

Config section `[body]`. `body.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `weight_kg` | number | kg | no | at least 0 | 25 to 300 | average |  |
| `body_fat_pct` | number | % | no | 0 to 100 | 3 to 60 | average |  |
| `waist_cm` | number | cm | no | at least 0 | 40 to 200 | average |  |
| `height_cm` | number | cm | no | at least 0 | 50 to 250 | average |  |

### Fitness markers

Config section `[fitness_markers]`. `fitness_markers.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `vo2max_ml_kg_min` | number | ml/kg/min | no | at least 0 | 10 to 90 | latest | higher |

- `vo2max_ml_kg_min`: Only estimates based on the person's own workouts. Skip a starting value a source fills in from age, sex or weight.
- `vo2max_ml_kg_min` is flagged as stuck if it stays flat while `heart.resting_hr_bpm` or `activity.active_min` moves.

### Vitals

Config section `[vitals]`. `vitals.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `systolic_mmhg` | number | mmHg | no | at least 0 | 70 to 220 | average |  |
| `diastolic_mmhg` | number | mmHg | no | at least 0 | 40 to 140 | average |  |
| `spo2_pct` | number | % | no | 0 to 100 | 80 to 100 | average |  |
| `respiratory_rate_brpm` | number | breaths/min | no | at least 0 | 6 to 40 | average |  |
| `skin_temp_c` | number | °C | no | at least 0 | 30 to 40 | average |  |
| `skin_temp_delta_c` | number | °C | no |  | -3 to 3 | average |  |

- `skin_temp_c`: Skin or wrist temperature as measured, e.g. overnight.
- `skin_temp_delta_c`: Change from the source's own baseline. Don't work out a baseline yourself; leave it empty when the source gives none.

### Nutrition

Config section `[nutrition]`. `nutrition.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `energy_in_kcal` | number | kcal | no | at least 0 | 0 to 8,000 | average |  |
| `protein_g` | number | g | no | at least 0 | 0 to 1,000 | average |  |
| `carbs_g` | number | g | no | at least 0 | 0 to 1,000 | average |  |
| `fat_g` | number | g | no | at least 0 | 0 to 1,000 | average |  |
| `water_ml` | number | ml | no | at least 0 | 0 to 10,000 | average | higher |
| `caffeine_mg` | number | mg | no | at least 0 | 0 to 1,500 | average | lower |
| `alcohol_drinks` | number | drinks | no | at least 0 | 0 to 30 | total | lower |

### Mindfulness

Config section `[mindfulness]`. `mindfulness.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `mindful_min` | number | min | no | 0 to 1,440 |  | total | higher |

### Menstrual cycle

Config section `[cycle]`. `cycle.csv`, one row per day, unique: `date`, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `flow_level` | number | 0-3 | no | 0 to 3 |  | days above 0 |  |
| `bbt_c` | number | °C | no | at least 0 | 35 to 38 | average |  |

- `flow_level`: 0 none, 1 light, 2 medium, 3 heavy. Leave it empty on a period day whose amount wasn't recorded; the row still counts as a period day.

### Medication

Config section `[medication]`. `medication.csv`, one row per day, unique: `date`, `item`, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `item` | text | | yes | | | | |
| `source` | text | | yes | | | | |
| `doses` | number | doses | no | at least 0 | 0 to 20 | total |  |

### Symptoms

Config section `[symptoms]`. `symptoms.csv`, one row per day, unique: `date`, `symptom`, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `symptom` | text | | yes | | | | |
| `source` | text | | yes | | | | |
| `severity` | number | 0-10 | no | 0 to 10 |  | average | lower |

- `severity`: 0 (none) to 10 (worst). Leave it empty when the source records only that the symptom was present. For a source with named levels, `sources.md` records the number each level gets.

### Blood glucose

Config section `[glucose]`. `glucose.csv`, one row per day, unique: `date`, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `glucose_mean_mmol_l` | number | mmol/L | no | at least 0 | 2 to 25 | average |  |
| `time_in_range_pct` | number | % | no | 0 to 100 |  | average |  |

- `time_in_range_pct`: Share of the day's continuous glucose monitor (CGM) readings from 3.9 to 10.0 mmol/L (70 to 180 mg/dL), the [international consensus](https://doi.org/10.2337/dci19-0028) range. Leave it empty without a CGM: a few finger-prick readings don't make a share of the day.

### Mood

Config section `[mood]`. `mood.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `mood` | number | 1-5 | no | 1 to 5 |  | average | higher |
| `energy` | number | 1-5 | no | 1 to 5 |  | average | higher |
| `stress` | number | 1-5 | no | 1 to 5 |  | average | lower |

### Reflections

Config section `[reflections]`. `reflections/`, one text file per year, many entries a day, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `time` | local time | | yes | | | | |
| `text` | text | | yes | | | | |

### Time use

Config section `[time]`. `time.csv`, one row per day, unique: `date`, `category`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `category` | text | | yes | | | | |
| `source` | text | | yes | | | | |
| `hours` | number | h | no | 0 to 24 |  | total |  |

- Overlapping time in one category counts once. Time in two categories at once goes to the one `sources.md` ranks first, so a day never adds up to more than 24 hours.
- Time from a calendar is time as scheduled. A day with no row has no tracked time; don't write `0`.

### Screen time

Config section `[screen_time]`. `screen_time.csv`, one row per day, unique: `date`, expected every day (gaps are reported).

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `screen_min` | number | min | no | 0 to 1,440 |  | average | lower |
| `pickups` | number | pickups | no | at least 0 | 0 to 1,000 | average | lower |

### Tasks

Config section `[tasks]`. `tasks.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `tasks_done` | number | tasks | no | at least 0 | 0 to 200 | total | higher |

### Habits

Config section `[habits]`. `habits.csv`, one row per day, unique: `date`, `habit`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `habit` | text | | yes | | | | |
| `source` | text | | yes | | | | |
| `times` | number | times | no | at least 0 | 0 to 100 | days above 0 | higher |

### Reading

Config section `[reading]`. `reading.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `pages` | number | pages | no | at least 0 | 0 to 2,000 | total | higher |
| `reading_min` | number | min | no | 0 to 1,440 |  | total | higher |
| `books_finished` | number | books | no | at least 0 | 0 to 20 | total | higher |

### Learning

Config section `[learning]`. `learning.csv`, one row per day, unique: `date`, `subject`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `subject` | text | | yes | | | | |
| `source` | text | | yes | | | | |
| `learning_min` | number | min | no | 0 to 1,440 |  | total | higher |
| `lessons` | number | lessons | no | at least 0 | 0 to 100 | total | higher |

### Media

Config section `[media]`. `media.csv`, one row per day, unique: `date`.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `listening_min` | number | min | no | 0 to 1,440 |  | total |  |
| `episodes` | number | episodes | no | at least 0 | 0 to 50 | total |  |
| `films` | number | films | no | at least 0 | 0 to 20 | total |  |

### Finances

Config section `[finances]`. `finances.csv`, one row per transaction, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `category` | text | | yes | | | | |
| `account` | text | | no | | | | |
| `currency` | text | | yes | | | | |
| `description` | text | | no | | | | |
| `source` | text | | yes | | | | |
| `amount` | number |  | no |  |  | total |  |

- Amounts in a currency other than `home_currency` are flagged, not converted.

### Life events

Config section `[events]`. `events.csv`, one row per event.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `label` | text | | yes | | | | |
| `source` | text | | yes | | | | |

### Weather

Config section `[weather]`. `weather.csv`, one row per day, unique: `date`, expected every day (gaps are reported).

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `temp_mean_c` | number | °C | no |  | -50 to 50 | average |  |
| `daylight_h` | number | h | no | 0 to 24 |  | total |  |
| `precipitation_mm` | number | mm | no | at least 0 | 0 to 500 | total |  |

### Social

Config section `[social]`. `social.csv`, one row per day, unique: `date`, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `source` | text | | yes | | | | |
| `social_h` | number | h | no | 0 to 24 |  | total |  |

- `social_h`: Time spent with other people. It can overlap `time.csv`; the two are never added together.

### Travel

Config section `[travel]`. `travel.csv`, one row per day, unique: `date`, sensitive.

| Column | Type | Unit | Required | Limits | Plausible | Summary | Better |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `date` | date | | yes | | | | |
| `country` | text | | no | | | | |
| `source` | text | | yes | | | | |
| `travel_day` | number | days | no | 0 to 1 |  | days above 0 |  |

<!-- categories:end -->
