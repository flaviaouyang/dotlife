# Source guides

One guide per data source: how to get the data out and how it maps to [the format](../../FORMAT.md). dotlife doesn't import anything itself. You, or your agent with the `setup` skill, follow a guide to write a script that fills your files, and `make fresh` runs it from then on.

| Guide | Fills | Best repeatable route |
| --- | --- | --- |
| [Apple Health](apple-health.md) | activity, workouts, sleep, heart, body, fitness markers, vitals, nutrition, mindfulness, cycle, symptoms, glucose; partly medication and mood | A HealthKit app's scheduled export (no web API); the Health app's own export is by hand |
| [Google Health](google-health.md) (formerly Fitbit) | activity, workouts, sleep, heart, body, fitness markers, vitals, nutrition, glucose | Google Health API v4 |
| [Oura](oura.md) | activity, workouts, sleep, heart, vitals, fitness markers, mindfulness | Oura API v2 (OAuth) |
| [WHOOP](whoop.md) | sleep, heart, workouts, vitals, activity, body | WHOOP API v2 (OAuth) |
| [jrnl](jrnl.md) | reflections | Export a year with `--format txt` |
| [Obsidian daily notes](obsidian-daily-notes.md) | mood, habits, tasks, reflections | Read the vault's Markdown files |
| [Apple Calendar](apple-calendar.md) | time use; optionally events, social, travel | EventKit script on a Mac |
| [Google Calendar](google-calendar.md) | time use; optionally events, social, travel | Google Calendar API v3 |
| [Outlook calendar](outlook-calendar.md) | time use; optionally events, social, travel | Microsoft Graph `calendarView` |
| [Weather](weather.md) | weather | Open-Meteo's historical API; no account |
| [By hand](manual.md) | any category or custom metric | Rows you type into `data/sources/manual/` |
| [Inference](inference.md) | any metric your other data answers, e.g. dining out from finances, mood from reflections | A script for rules; your agent's `fetch` skill for text |

## Choosing a route

Most sources offer several ways to get the data out. Prefer them in this order, and move down only when the one above can't work for this person:

1. **Fully automatic.** A script that runs unattended under `make fresh`: an API with a sign-in done once, a local file or database, a scheduled export that lands in a folder. A one-time step by the person (signing in, granting a permission, installing an app) is fine; a step they repeat is not.
2. **Mostly automatic, with a small part for an agent.** A script does the work, and only a step a script can't do (a connector, reading text) is an `agent` step that the `fetch` skill runs.
3. **By hand, every time.** The person exports or copies something before each refresh, e.g. Apple Health's "Export All Health Data" or a calendar's `.ics` file. Offer it last, say in `sources.md` what they must do and how often, and still read it with a script.

A guide lists its routes in this order. Setting a source up starts at the top; if a route fails once in the person's own terminal for a reason you can't fix there (a macOS permission that never appears, an account that can't sign in), take the next one down rather than trying more variants, and record why in `sources.md`.

Each guide was checked against the source's own documentation on the date at its end. Products change: if a step no longer works, check the linked pages and update the guide.

When two sources report the same metric, keep one per metric and record which in your `sources.md` (see [One value per metric](../../FORMAT.md#one-value-per-metric)).
