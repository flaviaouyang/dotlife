# Obsidian daily notes

[Obsidian](https://obsidian.md) keeps notes as Markdown files in a local folder, and its Daily notes plugin creates one note per day. Daily notes are free-form, so what they can fill depends on how the person writes them: typically `mood.csv`, `habits.csv`, `tasks.csv` and `reflections/`, sometimes a custom metric.

Everything below is a convention the person picks during setup. Agree on it with them, write it into `sources.md` (property names, section headings, the time rule for reflections), and have the script follow only what is written there. Don't guess a meaning for notes that don't follow it.

## What it fills

| dotlife column | From | Notes |
| --- | --- | --- |
| `mood.mood`, `mood.energy`, `mood.stress` | Number properties in the note's frontmatter, e.g. `mood: 4` | Whole numbers 1 to 5. Other scales are not converted; see "Mapping to the format". |
| `habits.habit`, `habits.times` | Checkbox properties (`meditated: true`) or checklist items under an agreed heading | Checked is `1`, unchecked is `0`, absent is no row. |
| `tasks.tasks_done` | Completed tasks, `- [x]` | Counted per day by the note's date, or by the Tasks plugin's done date. |
| `reflections.time`, `reflections.text` | Text under an agreed heading, or lines that start with a time | Plain text only. A time must come from the note, never be invented. |
| `<custom>.value` | Any other Number property, e.g. `guitar_min: 30` | Needs a `[custom.<name>]` table in `config.toml`. |

## Getting the data out

### Read the vault's files (best for a script)

"Obsidian stores your notes as Markdown-formatted plain text files in a vault", and a vault is a local folder with its subfolders ([How Obsidian stores data](https://obsidian.md/help/data-storage)). A script can read the daily notes straight from that folder with no API, account or app running. Ask the person for the vault path and record it in `sources.md`.

To find the daily notes, look at the Daily notes plugin's settings in Obsidian ([Daily notes](https://obsidian.md/help/plugins/daily-notes)):

- **Date format.** By default a daily note is named after the date in `YYYY-MM-DD` format. The format uses Moment.js tokens and can contain `/` to make folders: `YYYY/MMMM/YYYY-MMM-DD` creates `2023/January/2023-Jan-01`. In Moment.js, `YYYY` is the four-digit year, `MM` and `DD` two-digit month and day, `MMMM` and `MMM` the full and short month name, and text in square brackets is literal ([Moment.js format](https://momentjs.com/docs/#/displaying/format/)). Turn the format into a pattern the script can parse; the note's date comes from its path, not from file timestamps.
- **New file location.** The folder daily notes are created in.
- **Template file location.** The note new daily notes start from. This is where the agreed properties and headings belong, so every new note has them.

Copy the format and folder into `sources.md`. If the person uses the Periodic Notes community plugin, it has its own folder, template and file name format settings ([Periodic Notes](https://github.com/liamcain/obsidian-periodic-notes)); read the daily settings there instead. Whether it overrides the core plugin's settings is not documented on that page.

### Obsidian CLI

Obsidian has a command line interface, switched on in Settings, General, "Command line interface". It needs installer version 1.12.7 or later and the app running, and has `daily:read`, `daily:path` (the expected path, even if the note doesn't exist yet) and `property:read` commands ([Obsidian CLI](https://obsidian.md/help/cli)). It is handy for checking where today's note lives, but reading files directly is simpler for a sync that covers past days and doesn't need the app open.

## Mapping to the format

### Dates

A daily note's date is the date in its file name, already a local date. Use it for every row taken from that note. Don't use file creation or modification times: notes get edited later, synced between devices, and copied.

### Mood, energy and stress

Properties are YAML at the top of the note, between `---` lines, one `name: value` per line. Number properties "must always be a literal number", and a property name has one type across the whole vault ([Properties](https://obsidian.md/help/properties)). A suggested template:

```yaml
---
mood: 4
energy: 3
stress: 2
---
```

- Write one `mood.csv` row per note that has at least one of the three, with `source` set to `obsidian`.
- An empty or missing property is an empty cell. A note without any of them gives no row.
- Values must be whole numbers 1 to 5. If the person's scale is different (1 to 10, words, emoji), agree on that before syncing; don't rescale or translate silently. A value outside 1 to 5 is an error for the validator, so report it rather than clamp it.

### Habits

Two conventions work; pick one and write it into `sources.md`.

- **Checkbox properties.** `meditated: true`. Checkbox properties are `true` or `false`, and an empty value is indeterminate ([Properties](https://obsidian.md/help/properties)). Write `times = 1` for `true`, `0` for `false`, and no row when the property is empty or absent.
- **A checklist under a heading**, e.g. `## Habits` followed by `- [x] Meditated`. In Obsidian, `- [ ]` is an open task and any character inside the brackets marks it complete ([Basic formatting syntax](https://obsidian.md/help/syntax)). Take the item's text as `habit`, `1` for complete and `0` for open. Keep habit names identical day to day; rename in `sources.md` if the person rewords them.

For counts rather than yes or no (`pushups: 3`), use a Number property and write its value to `times`.

### Tasks done

Count completed tasks, `- [x]` (or any non-space character in the brackets), per day. Which day is a choice:

- **By the note's date.** Every completed task in the daily note counts for that day. Simple, but a task ticked off later in an old note counts for the old day.
- **By done date.** With the Tasks community plugin, a completed task gets `✅ YYYY-MM-DD` unless "Set done date on every completed task" is switched off ([Tasks: Dates](https://publish.obsidian.md/tasks/Getting+Started/Dates)). In its Dataview format the done date is `[completion:: YYYY-MM-DD]` ([Tasks: Dataview format](https://publish.obsidian.md/tasks/Reference/Task+Formats/Dataview+Format)). Counting by done date can cover the whole vault, not just daily notes, and is the better choice when the plugin is in use. A completed task without a done date is then left out, not given a date.

Write one `tasks.csv` row per day with at least one completed task. A day with no completed tasks but a daily note can be `0` if the person agrees that a note with no ticked tasks means none were done; otherwise leave it out.

### Reflections

dotlife reflections are plain-text entries, each starting with a local time: `[2026-08-24 22:40] text`. A daily note has a date but often no time per paragraph. Agree on one of these and write it into `sources.md`:

- **Timestamped lines.** The person starts each reflection with a time, e.g. `- 22:40 Long walk after work. #health` under `## Reflections`. Combine the note's date with that time. Obsidian's Templates plugin can insert the current time with `{{time}}` (default `HH:mm`) ([Templates](https://obsidian.md/help/plugins/templates)), which makes the habit easy.
- **One entry per note at a fixed time the person chooses**, e.g. all text under `## Reflections` as one entry at 21:00. This is a convention, not a measurement: say so in `sources.md`, and use it only if the person picks it.
- **Leave it out.** Text with no time and no agreed rule is not copied.

Never take a time from file timestamps or make one up. Set `[reflections] time_format` to match what the script writes (the default `%Y-%m-%d %H:%M` fits the examples above), and write one `reflections/YYYY.txt` per year, entries sorted by time.

Daily notes are Markdown; reflections are plain text. Convert the text when copying it:

- Drop list markers and heading markers at line starts.
- Turn wikilinks into their visible text: `[[Bob]]` becomes `Bob`, `[[Bob Smith|Bob]]` becomes `Bob`.
- Drop formatting marks (`**`, `_`, `==`) and embeds (`![[...]]`).
- Keep `#tags`; dotlife reads `#` and `@` words as tags by default.
- A line in the body must not itself start with `[` followed by something that looks like a time, or dotlife reads it as a new entry.

Reflections are sensitive. Switch the category on only after the person agrees, and quote them only when asked.

### Dataview inline fields

If the person already uses Dataview, the same values can be inline fields: `mood:: 4` on its own line, or `[mood:: 4]` inside a sentence ([Dataview: Adding metadata](https://blacksmithgu.github.io/obsidian-dataview/annotation/add-metadata/)). A script can read them with a simple pattern. Obsidian's Number property type only applies to frontmatter ([Properties](https://obsidian.md/help/properties)), so for new setups properties are the safer choice.

### Source

Use `obsidian` in the `source` column for every row.

## Watch out for

- **Free text.** A note that doesn't follow the agreed conventions gives no data. Report notes the script couldn't read (e.g. `mood: good`) instead of guessing.
- **Missing stays missing.** A daily note that doesn't exist, or a property left blank, is a gap, not a `0`.
- **Property types.** A property name has one type across the vault ([Properties](https://obsidian.md/help/properties)). Check that `mood`, `energy` and `stress` are set to Number, so Obsidian's editor asks for a number.
- **Edits after the fact.** Old notes change. Re-read the whole period on each sync and rewrite the rows that come from Obsidian, rather than appending only new days.
- **Stray files.** Read only file names that match the date format, so copies and other notes in the folder are skipped.
- **Date format changes.** If the person changes the date format, older notes keep their old names. Record both formats in `sources.md`.
- **Templates.** A note created from the template but never filled in may hold placeholder values. Agree with the person whether template defaults (e.g. `mood:` left blank) mean "not recorded"; they should.
- **Other sources.** If a mood or habit app also fills these files, `sources.md` decides which ranks higher.

## Not in the format

- Free-form prose outside the agreed reflections section.
- Text or List properties (e.g. `weather: rainy`, `people: [...]`): dotlife has no column for them.
- Open tasks, due and scheduled dates from the Tasks plugin: only completed tasks have a column.
- Links between notes and backlinks.
- Weekly and monthly notes from Periodic Notes: dotlife works with daily rows.

## Sources

- [Obsidian Help: Daily notes](https://obsidian.md/help/plugins/daily-notes)
- [Obsidian Help: Properties](https://obsidian.md/help/properties)
- [Obsidian Help: Templates](https://obsidian.md/help/plugins/templates)
- [Obsidian Help: Basic formatting syntax](https://obsidian.md/help/syntax)
- [Obsidian Help: How Obsidian stores data](https://obsidian.md/help/data-storage)
- [Obsidian Help: Obsidian CLI](https://obsidian.md/help/cli)
- [Moment.js: Format](https://momentjs.com/docs/#/displaying/format/)
- [Tasks plugin: Dates](https://publish.obsidian.md/tasks/Getting+Started/Dates)
- [Tasks plugin: Dataview format](https://publish.obsidian.md/tasks/Reference/Task+Formats/Dataview+Format)
- [Dataview: Adding metadata](https://blacksmithgu.github.io/obsidian-dataview/annotation/add-metadata/)
- [Periodic Notes (GitHub)](https://github.com/liamcain/obsidian-periodic-notes)

Checked 2026-10-29.
