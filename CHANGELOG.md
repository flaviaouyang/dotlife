# Changelog

What changed in each release of dotlife, for the people who use it. While dotlife is in beta, things can still change between releases.

## [0.1.0-beta.1](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-beta.1) - 3 November 2026

[All changes since 0.1.0-alpha.10](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.10...v0.1.0-beta.1)

### 📖 Docs

- Add prerequisites and a clone step to the quick start, and a coffee link
- Call dotlife a beta

## [0.1.0-alpha.10](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.10) - 1 November 2026

[All changes since 0.1.0-alpha.9](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.9...v0.1.0-alpha.10)

### ✨ New

- Tick menu options with enter, move on with Next, and colour the hints
- Say when a failed step's rows are from
- Ask plain setup questions for the agent to interpret, and add setup --finish

### 🐛 Fixed

- Correct metadata key references for typed-in values and VO2 max in Apple Health documentation

### 📖 Docs

- Update README for clarity and accuracy in project description
- Prefer the most automatic route, and keep agents off permissions

## [0.1.0-alpha.9](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.9) - 30 October 2026

[All changes since 0.1.0-alpha.8](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.8...v0.1.0-alpha.9)

### ✨ New

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

### 🐛 Fixed

- Count categories and sources in the right number
- Load pandas at start-up so switching pages doesn't break charts
- Keep the comment after [sources] in place when setup rewrites it
- Name agent steps as the fetch skill's, not as left undone

### 📖 Docs

- Settle Apple Health's choices, clock changes, zeros and rounding
- Describe staging in every source guide
- Add a finished sources.md example, checked against dotlife setup
- Settle when a source script fails, and Oura's choices

## [0.1.0-alpha.8](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.8) - 30 October 2026

[All changes since 0.1.0-alpha.7](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.7...v0.1.0-alpha.8)

### ✨ New

- **Dashboard:** Choose each Trends chart by what its numbers are
- **Dashboard:** Show reflections 20 to a page
- **Dashboard:** Divide pinned cards from the rest on the Overview

## [0.1.0-alpha.7](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.7) - 29 October 2026

[All changes since 0.1.0-alpha.6](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.6...v0.1.0-alpha.7)

### ✨ New

- Define what each column holds, and add height, absolute skin temperature and event sources
- Reject a day whose time across rows adds up to more than a day
- Count a period day with no recorded flow
- Add dotlife fresh and make fresh to run source scripts, then validate
- Label inferred values and show how many days were inferred
- Switch off untracked categories with a track list in config.toml
- Add dotlife setup, with arrow-key questions or an agent's answers

### 🐛 Fixed

- Count a day as watch-off only with both few steps and little sedentary time
- Read reflection stars and tags the way jrnl writes them

### 📖 Docs

- Add source guides for nine sources
- Plan setup, make fresh, fetch and maintain in place of setup-sources and sync
- Add the inference guide
- Add the weather guide

## [0.1.0-alpha.6](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.6) - 29 October 2026

[All changes since 0.1.0-alpha.5](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.5...v0.1.0-alpha.6)

### ✨ New

- Pin or hide cards and categories from a card menu
- Pin or hide Overview cards and Trends categories separately
- Colour cards green for good, orange for bad and blue for neutral

## [0.1.0-alpha.5](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.5) - 29 October 2026

[All changes since 0.1.0-alpha.4](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.4...v0.1.0-alpha.5)

### ✨ New

- Show the cycle as a calendar strip and spending against budgets

### 📖 Docs

- Add dashboard screenshots to the README

## [0.1.0-alpha.4](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.4) - 29 October 2026

[All changes since 0.1.0-alpha.3](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.3...v0.1.0-alpha.4)

### 💥 Breaking changes

- Replace the journal with yearly reflections files

### ✨ New

- Add goals to config, cards and trend charts
- Pin Overview cards, saved in config.toml
- Replace card sparklines with charts suited to each metric
- Lay out reflections like a diary, with highlighted search
- Underline the author credit on hover

### 🐛 Fixed

- Show life events as hover lines so labels can't overlap
- Draw card charts that have a usual-range band
- Keep the theme menu and draw card charts for light and dark mode
- Show the dotlife favicon in Safari
- Keep the logo visible in dark mode

### 📖 Docs

- Credit the author in the dashboard and README

## [0.1.0-alpha.3](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.3) - 29 October 2026

[All changes since 0.1.0-alpha.2](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.2...v0.1.0-alpha.3)

### ✨ New

- Add the journal reader and the summary calculations
- Load a data folder once into a dataset
- Add the dotlife dashboard command and app shell
- Build the Overview, Trends, Journal and Data health pages
- Add the dotlife logo and favicon to the dashboard

### 🐛 Fixed

- Stop sample journal entries naming the wrong weekday.

### 📖 Docs

- Update performance guideline to use polars instead of pandas in the dashboard
- Show the logo at the top of the README

## [0.1.0-alpha.2](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.2) - 29 October 2026

[All changes since 0.1.0-alpha.1](https://github.com/flaviaouyang/dotlife/compare/v0.1.0-alpha.1...v0.1.0-alpha.2)

### ✨ New

- Add config defaults for display, dashboard, stale values and finances
- Mark categories expected every day and flag foreign currencies
- Add the validator and the dotlife validate command
- Group repeated problems in the validator report
- Let a data folder carry its own config.toml
- Add Sherlock Holmes sample data
- Make Alice of Alice and Bob the sample persona

### 📖 Docs

- Restyle README
- Add FORMAT.md, generated from the category specs

## [0.1.0-alpha.1](https://github.com/flaviaouyang/dotlife/releases/tag/v0.1.0-alpha.1) - 29 October 2026

### ✨ New

- Add periods, category schema and first category specs
- Define all 27 categories with hard limits and plausible bounds

### 📖 Docs

- Add agent instructions
- Describe the dotlife package layout
- Split agent instructions from contributor guide
