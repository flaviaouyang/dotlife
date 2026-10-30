# By hand

Anything without an app or device can be entered by hand: a waist measurement once a month, a mood rating, pages read, a habit. Hand entries are a source like any other, called `manual`, so they can fill a category on their own or sit alongside an app, ranked against it.

## What it fills

Any category, and any custom metric. Use the columns `FORMAT.md` lists for it; a file can leave out metric columns you never fill.

## Where the rows go

Put them in `data/sources/manual/`, one file per category with the same name as the data file:

| Category | File |
| --- | --- |
| Body | `data/sources/manual/body.csv` |
| Mood | `data/sources/manual/mood.csv` |
| Reflections | `data/sources/manual/reflections/2026.txt` |
| A custom metric `guitar` | `data/sources/manual/guitar.csv` |

List `manual` for the category in `[sources]` (with `dotlife setup`, choose "By hand"). Then run `make fresh`: it merges your rows into `data/` with any other source's, and checks them. It works with no scripts at all.

Don't edit the files in `data/` themselves when a category has a source: `make fresh` rebuilds them and your edit would be lost. A category nothing stages for is left alone, but entering it in `sources/manual/` from the start means nothing has to move when you add an app later.

## Writing the rows

Any text editor works, and so does a spreadsheet saved as CSV (UTF-8, comma-separated). The first line is the header.

```csv
date,source,waist_cm
2026-03-01,manual,80.5
2026-04-05,manual,80
```

- `date` as `YYYY-MM-DD`, the local date. A night's sleep goes under the date you woke up.
- `source` is required: `manual`, or something more specific such as `tape-measure`. It is only a label; the folder is what makes the row a hand entry.
- Numbers in the column's unit (`waist_cm` is centimetres), without units or thousands separators.
- An empty cell is a value you didn't record. Never type `0` for "didn't measure".
- Sessions (sleep, workouts) need `start` and `end` with the UTC offset, e.g. `2026-03-08T23:10+01:00`.
- Reflections are plain text, one file a year, each entry starting with its time in brackets: `[2026-08-24 22:40] Long walk after work. #walking`. See [Reflections in FORMAT.md](../../FORMAT.md#reflections).

## Ranking against another source

`[sources]` decides who wins a day. For each date, the data file keeps the rows of the first listed source that has that date:

- `mood = ["manual", "inferred-reflections"]`: your rating wins; the inferred one fills days you didn't rate.
- `body = ["apple-health", "manual"]`: the scale wins; your row counts only on days with no scale reading. If your row had a value the scale's lacks, such as your waist, `make fresh` names it as left out, so you can rank `manual` first instead.

## Watch out for

- **A typo is still data.** Run `make fresh` after a batch of entries and read what the validator reports; it catches impossible values and flags unlikely ones.
- **One row per day** (per item, for files like habits or time). Two rows for the same date in one file are reported as duplicates.
- **Spreadsheets reformat dates and numbers.** Check that dates stay `YYYY-MM-DD` and decimals use a point after saving.
