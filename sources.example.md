<!-- An example of a finished sources.md, for Alice (of Alice and Bob), who is made up. Your own sources.md is written by `dotlife setup` and the setup skill. -->

# Sources

Where each kind of data comes from, which source wins when two report the same
thing, and the choices each source's guide leaves to you. `dotlife setup` writes
the part between the markers; the `setup` and `maintain` skills add the rest.

<!-- dotlife setup:start (written by `dotlife setup`) -->

## Sources

| Source | Guide | Fills |
| --- | --- | --- |
| Apple Health | [apple-health.md](docs/sources/apple-health.md) | Activity, Workouts, Sleep, Heart, Body, Fitness markers, Mindfulness |
| By hand | [manual.md](docs/sources/manual.md) | Body, Mood |
| Inferred from reflections (AI) | [inference.md](docs/sources/inference.md) | Mood |
| jrnl | [jrnl.md](docs/sources/jrnl.md) | Reflections |
| Open-Meteo | [weather.md](docs/sources/weather.md) | Weather |

## Which source wins

- Body: Apple Health over By hand
- Mood: By hand over Inferred from reflections (AI)

<!-- dotlife setup:end -->

## Apple Health

How the data gets out: on her iPhone, Alice opens Health, taps her picture, taps Export All Health Data and saves `export.zip` into `inbox/` in this repo, replacing the old one. Then she runs `make fresh`. The export is all or nothing, so `scripts/apple_health.py` re-reads the whole file every run. No account or secret is involved.

Settings, under `[apple-health]` in `config.toml`: `export = "inbox/export.zip"`, `sleep_gap_min = 60` and `apps = { "Health Mate" = "withings" }`.

Choices:

- **Devices:** an Apple Watch, worn most of the day and at night, and an iPhone. The watch wins for every category. On a date the watch has nothing for a category, the iPhone's row is used, with `source` set to `iphone`; the two are never added. `fallback_sources = ["iphone"]` under `[activity]` keeps those days out of averages.
- **Other apps' data:** weight from her Withings scale, written to Health by the Health Mate app (`source` set to `withings`), wins on any day it has a reading. Weight she typed into Health fills only days without one (`source` set to `entered-in-health`). No other app's data is used.
- **Sleep gap:** an hour. Samples further apart start a new session.
- **Symptom severities:** not needed; she doesn't track symptoms.
- **How far back:** everything in the export.

How the guide's mapping is applied:

- `activity.active_min` is Apple's exercise minutes.
- `heart.hrv_ms` is SDNN up to 2026-09-14 and RMSSD from then on, when her watch started writing it. Expect a step in the chart there.
- `vitals` isn't tracked, so the blood pressure in her export is ignored.

Differences from the guide: none.

## By hand

Rows Alice adds herself, in `data/sources/manual/`, in the format:

- `body.csv`: her waist, measured on the first Sunday of each month. The scale's row wins on a day with both, and `make fresh` says when a waist measurement was left out because of it.
- `mood.csv`: a 1 to 5 rating on days she remembers to give one. It wins over the inferred mood.

## Inferred from reflections (AI)

Mood on days she gave no rating is read from her reflections by her coding agent. She chose this knowing that her reflections go to the agent's model provider each time.

- Instructions: `prompts/mood.md`, asking for a 1 to 5 rating from what the day's entries say, and none when they don't speak to mood.
- Answers: `inferred/mood.csv`, with a few words of evidence per day. A day already answered isn't asked again.
- `config.toml` lists the agent step `mood-from-reflections` and then the script `scripts/mood_inferred.py`, which stages the answers as `inferred-reflections`. The fetch skill does the agent step; `make fresh` only runs the script.

## jrnl

Her journal is one plain-text jrnl file, not encrypted, at the path `jrnl --list` shows, under `[jrnl] journal` in `config.toml`. `scripts/jrnl.py` splits it by year into `data/sources/jrnl/reflections/`, replacing the current year's file each run, so edits made in jrnl carry over.

- Journals: only her default journal; her `work` journal stays out.
- Time format: jrnl's default, so `[reflections] time_format = "%Y-%m-%d %I:%M:%S %p"`.
- Tags: jrnl's default symbols, `#@`, the same as dotlife's.

## Open-Meteo

Weather for home, from Open-Meteo's historical API, with no account. The location under `[weather]` is rounded to two decimals. `scripts/weather.py` fetches from 7 days before yesterday to yesterday each run, and staged everything from 2026-01-01 on the first run. Weather data by Open-Meteo.com, licensed CC BY 4.0: credit it when sharing a chart.
