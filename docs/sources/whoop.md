# WHOOP

WHOOP is a screenless wrist or body strap with a phone app and a public developer API. It can fill `sleep.csv`, `heart.csv`, `workouts.csv`, `vitals.csv` (SpO2, respiratory rate and skin temperature), `activity.csv` (steps and energy, per WHOOP cycle) and, loosely, `body.csv` (weight and height).

## What it fills

All field names below are from the v2 API ([API reference](https://developer.whoop.com/api/), [OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)).

| dotlife column | From | Notes |
| --- | --- | --- |
| `sleep.start`, `sleep.end` | Sleep `start`, `end` | UTC timestamps; `timezone_offset` gives the person's offset at the time. |
| `sleep.asleep_min` | Sleep `score.stage_summary`: `total_light_sleep_time_milli` + `total_slow_wave_sleep_time_milli` + `total_rem_sleep_time_milli` | Milliseconds; divide by 60,000. |
| `sleep.deep_min` | `total_slow_wave_sleep_time_milli` | WHOOP calls deep sleep slow wave sleep (SWS). |
| `sleep.rem_min` | `total_rem_sleep_time_milli` | |
| `sleep.light_min` | `total_light_sleep_time_milli` | |
| `sleep.awake_min` | `total_awake_time_milli` | |
| `heart.resting_hr_bpm` | Recovery `score.resting_heart_rate` | One recovery per cycle, tied to a sleep by `sleep_id`. |
| `heart.hrv_ms` | Recovery `score.hrv_rmssd_milli` | RMSSD in milliseconds, so no conversion. |
| `vitals.spo2_pct` | Recovery `score.spo2_percentage` | Only on WHOOP 4.0 or later. |
| `vitals.respiratory_rate_brpm` | Sleep `score.respiratory_rate` | Per sleep; use the main (non-nap) sleep. |
| `vitals.skin_temp_c` | Recovery `score.skin_temp_celsius` | Absolute °C. Only on WHOOP 4.0 or later. |
| `vitals.skin_temp_delta_c` | Leave empty | The API gives no deviation from a baseline (see below). |
| `workouts.start`, `workouts.end`, `workouts.type` | Workout `start`, `end`, `sport_name` | |
| `workouts.avg_hr_bpm` | Workout `score.average_heart_rate` | bpm. |
| `workouts.distance_m` | Workout `score.distance_meter` | Only present if distance data was sent to WHOOP. |
| `workouts.energy_kcal` | Workout `score.kilojoule` | Divide by 4.184. As reported. |
| `activity.steps` | Cycle `step_count` | Per WHOOP cycle, not per calendar day (see below). |
| `activity.energy_kcal` | Cycle `score.kilojoule` | Per cycle; divide by 4.184. The docs don't say whether it includes resting energy; see below. |
| `body.weight_kg` | Body measurement `weight_kilogram` | A single current value with no date; see below. |
| `body.height_cm` | Body measurement `height_meter` | Metres; multiply by 100. A single current value with no date, like weight. |

## Getting the data out

### Developer API (best for a repeatable script)

The current API is v2. WHOOP's docs say "The v1 API is no longer supported and any new features or functionality will be added to v2 only", and v1 webhooks have been removed ([v1 to v2 migration](https://developer.whoop.com/docs/developing/v1-v2-migration)). Sleep and workout IDs are UUIDs in v2. The old integer `v1_id` and the workout `sport_id` are documented as "Will not exist past 09/01/2025" ([OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)), so use `sport_name`.

Setup:

1. Sign in to the [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com) with a WHOOP account. You may be asked to create a team first. Create an app, choose its scopes and add at least one redirect URL. You get a client ID and client secret. You can create up to 5 apps ([Getting started](https://developer.whoop.com/docs/developing/getting-started/)).
2. Run the OAuth 2.0 authorisation code flow. Authorisation URL `https://api.prod.whoop.com/oauth/oauth2/auth`, token URL `https://api.prod.whoop.com/oauth/oauth2/token`. Request the `offline` scope to get a refresh token. Access tokens last a short time (`expires_in`, in seconds), and each refresh returns a new refresh token that replaces the old one, so store the newest. If you generate the `state` parameter yourself it must be eight characters long ([OAuth](https://developer.whoop.com/docs/developing/oauth/)).
3. Scopes needed: `read:sleep`, `read:recovery`, `read:workout`, `read:cycles`, `read:body_measurement`, plus `offline` ([API reference](https://developer.whoop.com/api/)).

Endpoints, all under `https://api.prod.whoop.com/developer` ([API reference](https://developer.whoop.com/api/)):

| Data | Endpoint | Scope |
| --- | --- | --- |
| Cycles | `GET /v2/cycle`, `GET /v2/cycle/{cycleId}` | `read:cycles` |
| Sleep for a cycle | `GET /v2/cycle/{cycleId}/sleep` | `read:sleep` |
| Recovery | `GET /v2/recovery`, `GET /v2/cycle/{cycleId}/recovery` | `read:recovery` |
| Sleeps | `GET /v2/activity/sleep`, `GET /v2/activity/sleep/{sleepId}` | `read:sleep` |
| Workouts | `GET /v2/activity/workout`, `GET /v2/activity/workout/{workoutId}` | `read:workout` |
| Height, weight, max HR | `GET /v2/user/measurement/body` | `read:body_measurement` |

Collection endpoints take `limit` (at most 25, default 10), `start` (inclusive), `end` (exclusive, defaults to now) and `nextToken`. Pass the response's `next_token` as `nextToken` until it is absent. Results come newest first; recovery is sorted by the start of its sleep ([OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)).

Rate limits are 100 requests a minute and 10,000 a day by default. Over the limit you get `429`; the `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers tell you where you stand. Increases can be requested from the dashboard ([Rate limiting](https://developer.whoop.com/docs/developing/rate-limiting/)). With 25 records a page, a year of daily sleeps, recoveries and cycles is roughly 45 requests, so a full backfill fits easily.

### Data export from the app (one-off, by hand)

In the WHOOP app: More, then App Settings, then Data Export, then Create Export. WHOOP emails a download link, which can take up to 24 hours ([WHOOP Community answer](https://www.community.whoop.com/t/can-i-export-my-strain-data-to-a-spreadsheet-or-another-platform-detail/149)). A third-party guide gives the Android path as More, then Data Export, and reports a newer flow with a date-range picker ([Gneta guide](https://www.gneta.app/blog/export-whoop-data-guide)); WHOOP's own help article ([How to Export Your Data](https://support.whoop.com/s/article/How-to-Export-Your-Data)) did not load for checking, so confirm in the app.

The export is a set of CSV files: `physiological_cycles`, `sleeps`, `workouts` and `journal_entries`, per a member's report ([WHOOP Community thread](https://www.community.whoop.com/t/expose-step-count-in-the-developer-api-and-the-data-export/16226)). The exact column headers are not documented in any page checked; read them from the header row of an actual export before mapping. That same thread says the export has no steps. Use the export to backfill history by hand; use the API for anything repeatable.

### Connectors in AI tools

No official WHOOP connector or MCP server was found. Several community MCP servers wrap the v2 API with your own developer app credentials; one deploy page says it "isn't affiliated with or endorsed by WHOOP" ([Railway template](https://railway.com/deploy/whoop-mcp-server-whoop-data-in-claude-chatgpt--whoop-mcp-claude)). Since the API can be scripted, a connector is not needed.

## Mapping to the format

**WHOOP cycles are not days.** WHOOP files everything under a physiological cycle that runs from one sleep onset to the next, not midnight to midnight ([Cycle](https://developer.whoop.com/docs/developing/user-data/cycle), [WHOOP engineering blog](https://engineering.prod.whoop.com/dev-platform-2/)). The current cycle has a `start` and no `end`. Past cycle boundaries "may change for a few days" as WHOOP learns more. dotlife's `cycle.csv` is the menstrual cycle and has nothing to do with WHOOP cycles.

- **Time zone.** API timestamps are UTC (e.g. `2026-03-08T05:40:12.000Z`). Write `start` and `end` with an offset (UTC is fine, or apply `timezone_offset`), and compute `date` in the time zone from `config.toml`.
- **Sleep.** One row per sleep with `score_state` = `SCORED`, filed under the local date of `end` (the wake date). Naps (`nap` = true) are their own sessions and can be written as their own rows; the dashboard treats the longest session of a date as the main one. Leave the stage columns empty for `PENDING_SCORE` or `UNSCORABLE` sleeps.
- **Heart, SpO2 and skin temperature.** Each recovery has a `sleep_id`. File its `resting_heart_rate`, `hrv_rmssd_milli`, `spo2_percentage` and `skin_temp_celsius` under the wake date of that sleep. WHOOP calculates recovery when you wake up ([Recovery](https://developer.whoop.com/docs/developing/user-data/recovery)). Not every cycle has a recovery, e.g. when the strap wasn't worn ([Get current recovery score](https://developer.whoop.com/docs/tutorials/get-current-recovery-score)); leave those dates empty.
- **Respiratory rate.** From the main (non-nap) sleep of each wake date.
- **Skin temperature.** The API's `skin_temp_celsius` is "The user's skin temperature, in Celsius" ([OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)), an absolute value such as `33.7`, so it goes in `skin_temp_c`. `skin_temp_delta_c` is a change from the source's own baseline, which WHOOP's API does not provide. Leave that column empty rather than computing a baseline.
- **Workouts.** One row per workout, filed under the local date of `start`. `type` is `sport_name` as given (e.g. `running`). `energy_kcal` = `kilojoule` / 4.184, since a calorie is 4.184 joules ([NIST](https://www.nist.gov/glossary-term/19621)). `distance_m` from `distance_meter` only when present. v2 also returns recovery activities as workouts ([v1 to v2 migration](https://developer.whoop.com/docs/developing/v1-v2-migration)); keep or drop them as the person prefers.
- **Activity.** Cycle `step_count` is in the API spec ([OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)); a reply in the community thread dates it to 23 September 2026 ([WHOOP Community thread](https://www.community.whoop.com/t/expose-step-count-in-the-developer-api-and-the-data-export/16226)). It is a cycle total and is null "when no step data exists for the cycle (e.g. the device was not worn for the full cycle)". A cycle is a source's own day, so follow [Days, weeks and months in FORMAT.md](../../FORMAT.md#days-weeks-and-months): don't split it, and file each ended cycle under the date the person woke up at its start, i.e. the wake date of the sleep that opens it (`GET /v2/cycle/{cycleId}/sleep`). Skip the current cycle (no `end`) until it ends. The same goes for `energy_kcal` from the cycle's `kilojoule`.
- **Energy.** `energy_kcal` should be total energy, active plus resting. The spec says only "Kilojoules the user expended during the cycle" ([OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)) and doesn't say whether that includes resting energy. Write it as given and record in `sources.md` that WHOOP doesn't document whether it is total energy.
- **Weight and height.** `GET /v2/user/measurement/body` returns one current `weight_kilogram` and `height_meter` ("User's height in meters") with no date, and the docs don't say where they come from ([OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)). Write each under the sync date only when it differs from the last WHOOP value written. A smart scale wins on any day it has a reading.
- **Source.** Write `whoop`.

Example rows (made up):

```csv
date,start,end,source,asleep_min,deep_min,rem_min,light_min,awake_min
2026-03-08,2026-03-07T22:51Z,2026-03-08T06:32Z,whoop,431,98,112,221,30
```

## Watch out for

- **Rescoring.** Scores arrive as `PENDING_SCORE` first, and past cycle boundaries can move for a few days. Re-fetch the last week on each sync and overwrite WHOOP's rows for those dates.
- **Cycle versus calendar day.** A late night pushes the next sleep onset, so a cycle's steps and energy can run well past midnight. Expect daily totals that don't match other devices.
- **Recovery and naps.** Map recovery by `sleep_id`, not by date, so a nap never picks up the night's HRV.
- **Calibration.** Recovery has `user_calibrating`; for a new member the values may be less reliable. The values are still real readings, so keep them.
- **Hardware.** `spo2_percentage` and `skin_temp_celsius` are only present on WHOOP 4.0 or later.
- **Repeated weight and height.** The body measurement endpoint returns the same values every time until they change. Don't write them again as new readings.
- **Rate limits.** 100 requests a minute; back off on `429`.
- **Export gaps.** The app export has no steps, and its column names are undocumented.

## Not in the format

- Recovery score (0 to 100%), from recovery `score.recovery_score`.
- Day strain (0 to 21) per cycle, `score.strain`, and workout strain.
- Cycle average and max heart rate, `score.average_heart_rate`, `score.max_heart_rate`.
- Sleep performance, consistency and efficiency percentages, and sleep need (`score.sleep_needed`).
- Sleep cycle count and disturbance count, `sleep_cycle_count`, `disturbance_count`.
- Time in bed and time with no data, `total_in_bed_time_milli`, `total_no_data_time_milli`.
- Workout heart rate zone durations (`zone_zero_milli` to `zone_five_milli`), max heart rate and altitude gain.
- WHOOP's calculated max heart rate.
- Journal entries (self-logged behaviours), export only.

## Sources

- [WHOOP API reference](https://developer.whoop.com/api/)
- [WHOOP API OpenAPI spec](https://api.prod.whoop.com/developer/doc/openapi.json)
- [WHOOP Developer: v1 to v2 migration](https://developer.whoop.com/docs/developing/v1-v2-migration)
- [WHOOP Developer: Getting started](https://developer.whoop.com/docs/developing/getting-started/)
- [WHOOP Developer: OAuth](https://developer.whoop.com/docs/developing/oauth/)
- [WHOOP Developer: Rate limiting](https://developer.whoop.com/docs/developing/rate-limiting/)
- [WHOOP Developer: Cycle](https://developer.whoop.com/docs/developing/user-data/cycle)
- [WHOOP Developer: Recovery](https://developer.whoop.com/docs/developing/user-data/recovery)
- [WHOOP Developer: Sleep](https://developer.whoop.com/docs/developing/user-data/sleep)
- [WHOOP Developer: Workout](https://developer.whoop.com/docs/developing/user-data/workout)
- [WHOOP Developer: Get current recovery score](https://developer.whoop.com/docs/tutorials/get-current-recovery-score)
- [WHOOP Engineering: Your body doesn't know what day it is](https://engineering.prod.whoop.com/dev-platform-2/)
- [WHOOP Support: How to Export Your Data](https://support.whoop.com/s/article/How-to-Export-Your-Data) (did not render when checked)
- [WHOOP Community: Can I export my Strain data to a spreadsheet or another platform?](https://www.community.whoop.com/t/can-i-export-my-strain-data-to-a-spreadsheet-or-another-platform-detail/149) (community)
- [WHOOP Community: Expose step count in the Developer API and the data export](https://www.community.whoop.com/t/expose-step-count-in-the-developer-api-and-the-data-export/16226) (community)
- [Gneta: Export WHOOP data guide](https://www.gneta.app/blog/export-whoop-data-guide) (third party)
- [Railway: Whoop MCP Server template](https://railway.com/deploy/whoop-mcp-server-whoop-data-in-claude-chatgpt--whoop-mcp-claude) (third party)
- [NIST glossary: Calorie](https://www.nist.gov/glossary-term/19621)

Checked 2026-10-29.
