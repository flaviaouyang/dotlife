# Changelog

What changed in each release of dotlife, for the people who use it.

## [0.1.0-alpha.9] - 2026-10-30

### Features

- Let source scripts stage rows per source, and merge them by rank in make fresh
- Add the setup skill
- Name values the merge leaves out when a higher-ranked source has the day
- Leave days from a fallback device out of averages
- Merge and validate hand entries even without source scripts, with a guide to them
- Warn about rows dated after today
- Add the maintain skill
- Rank sleep and workouts by overlapping time when merging sources
- Warn about reflections timed after now
- Add the fetch skill

### Bug fixes

- Count categories and sources in the right number
- Load pandas at start-up so switching pages doesn't break charts
- Keep the comment after [sources] in place when setup rewrites it
- Name agent steps as the fetch skill's, not as left undone

### Documentation

- Settle Apple Health's choices, clock changes, zeros and rounding
- Describe staging in every source guide
- Add a finished sources.md example, checked against dotlife setup
- Settle when a source script fails, and Oura's choices

## [0.1.0-alpha.8] - 2026-10-30

### Features

- **dashboard:** Choose each Trends chart by what its numbers are
- **dashboard:** Show reflections 20 to a page
- **dashboard:** Divide pinned cards from the rest on the Overview

## [0.1.0-alpha.7] - 2026-10-29

### Features

- Define what each column holds, and add height, absolute skin temperature and event sources
- Reject a day whose time across rows adds up to more than a day
- Count a period day with no recorded flow
- Add dotlife fresh and make fresh to run source scripts, then validate
- Label inferred values and show how many days were inferred
- Switch off untracked categories with a track list in config.toml
- Add dotlife setup, with arrow-key questions or an agent's answers

### Bug fixes

- Count a day as watch-off only with both few steps and little sedentary time
- Read reflection stars and tags the way jrnl writes them

### Documentation

- Add source guides for nine sources
- Plan setup, make fresh, fetch and maintain in place of setup-sources and sync
- Add the inference guide
- Add the weather guide

## [0.1.0-alpha.6] - 2026-10-29

### Features

- Pin or hide cards and categories from a card menu
- Pin or hide Overview cards and Trends categories separately
- Colour cards green for good, orange for bad and blue for neutral

## [0.1.0-alpha.5] - 2026-10-29

### Features

- Show the cycle as a calendar strip and spending against budgets

### Documentation

- Add dashboard screenshots to the README

## [0.1.0-alpha.4] - 2026-10-29

### Features

- **Breaking:** Replace the journal with yearly reflections files
- Add goals to config, cards and trend charts
- Pin Overview cards, saved in config.toml
- Replace card sparklines with charts suited to each metric
- Lay out reflections like a diary, with highlighted search
- Underline the author credit on hover

### Bug fixes

- Show life events as hover lines so labels can't overlap
- Draw card charts that have a usual-range band
- Keep the theme menu and draw card charts for light and dark mode
- Show the dotlife favicon in Safari
- Keep the logo visible in dark mode

### Documentation

- Credit the author in the dashboard and README

## [0.1.0-alpha.3] - 2026-10-29

### Features

- Add the journal reader and the summary calculations
- Load a data folder once into a dataset
- Add the dotlife dashboard command and app shell
- Build the Overview, Trends, Journal and Data health pages
- Add the dotlife logo and favicon to the dashboard

### Bug fixes

- Stop sample journal entries naming the wrong weekday.

### Documentation

- Update performance guideline to use polars instead of pandas in the dashboard
- Show the logo at the top of the README

## [0.1.0-alpha.2] - 2026-10-29

### Features

- Add config defaults for display, dashboard, stale values and finances
- Mark categories expected every day and flag foreign currencies
- Add the validator and the dotlife validate command
- Group repeated problems in the validator report
- Let a data folder carry its own config.toml
- Add Sherlock Holmes sample data
- Make Alice of Alice and Bob the sample persona

### Documentation

- Restyle README
- Add FORMAT.md, generated from the category specs

## [0.1.0-alpha.1] - 2026-10-29

### Features

- Add periods, category schema and first category specs
- Define all 27 categories with hard limits and plausible bounds

### Documentation

- Add agent instructions
- Describe the dotlife package layout
- Split agent instructions from contributor guide
