# Source guides

One guide per data source: how to get the data out and how it maps to [the format](../../FORMAT.md). dotlife doesn't import anything itself. You, or your agent with the `setup-sources` skill, follow a guide to write a script that fills your files. Use a connector only where no script can reach the data.

| Guide | Fills | Best repeatable route |
| --- | --- | --- |
| [Apple Health](apple-health.md) | activity, workouts, sleep, heart, body, fitness markers, vitals, nutrition, mindfulness, cycle, symptoms, glucose; partly medication and mood | Export from the Health app (no web API) |
| [Google Health](google-health.md) (formerly Fitbit) | activity, workouts, sleep, heart, body, fitness markers, vitals, nutrition, glucose | Google Health API v4 |
| [Oura](oura.md) | activity, workouts, sleep, heart, vitals, fitness markers, mindfulness | Oura API v2 (OAuth) |
| [WHOOP](whoop.md) | sleep, heart, workouts, vitals, activity, body | WHOOP API v2 (OAuth) |
| [jrnl](jrnl.md) | reflections | Export a year with `--format txt` |
| [Obsidian daily notes](obsidian-daily-notes.md) | mood, habits, tasks, reflections | Read the vault's Markdown files |
| [Apple Calendar](apple-calendar.md) | time use; optionally events, social, travel | EventKit script on a Mac |
| [Google Calendar](google-calendar.md) | time use; optionally events, social, travel | Google Calendar API v3 |
| [Outlook calendar](outlook-calendar.md) | time use; optionally events, social, travel | Microsoft Graph `calendarView` |

Each guide was checked against the source's own documentation on the date at its end. Products change: if a step no longer works, check the linked pages and update the guide.

When two sources report the same metric, keep one per metric and record which in your `sources.md` (see [One value per metric](../../FORMAT.md#one-value-per-metric)).
