# Oura Ring

The Oura Ring is a smart ring with a phone app, a data export and a public API (v2). It can fill `sleep.csv`, `heart.csv`, `activity.csv`, `workouts.csv`, `vitals.csv` (SpO2, breathing rate, temperature deviation), `fitness_markers.csv` (VO2 max) and `mindfulness.csv`. It cannot fill `cycle.csv`.

## What it fills

All field names below are from the v2 API's OpenAPI spec ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json), shown at [API docs](https://cloud.ouraring.com/v2/docs)). "Long sleep" means the `sleep` document with `type` = `long_sleep` (see [Mapping to the format](#mapping-to-the-format)).

| dotlife column | From | Notes |
| --- | --- | --- |
| `sleep.start`, `sleep.end` | `sleep` `bedtime_start`, `bedtime_end` | Local time with offset. |
| `sleep.asleep_min` | `sleep` `total_sleep_duration` | Seconds; divide by 60. |
| `sleep.deep_min` | `sleep` `deep_sleep_duration` | Seconds; divide by 60. |
| `sleep.rem_min` | `sleep` `rem_sleep_duration` | Seconds; divide by 60. |
| `sleep.light_min` | `sleep` `light_sleep_duration` | Seconds; divide by 60. |
| `sleep.awake_min` | `sleep` `awake_time` | Seconds; divide by 60. |
| `heart.resting_hr_bpm` | Long sleep `average_heart_rate` | bpm. Not `lowest_heart_rate`; see below. |
| `heart.hrv_ms` | Long sleep `average_hrv` | Milliseconds, no conversion. |
| `vitals.spo2_pct` | `daily_spo2` `spo2_percentage.average` | Percent. Gen3 and later only. |
| `vitals.respiratory_rate_brpm` | Long sleep `average_breath` | "breaths/minute". |
| `vitals.skin_temp_c` | Leave empty | The API has no absolute temperature, only deviations ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). |
| `vitals.skin_temp_delta_c` | Long sleep `readiness.temperature_deviation` | °C from the person's baseline, as Oura reports it. Also in `daily_readiness`. |
| `activity.steps` | `daily_activity` `steps` | Per Oura activity day, which starts at 4 am; see below. |
| `activity.active_min` | Sum of `workout` durations per day | Oura's own measure is "activity time", built from activities; the API has no daily field for it. See below. |
| `activity.sedentary_min` | `daily_activity` `sedentary_time` | Seconds; divide by 60. |
| `activity.energy_kcal` | `daily_activity` `total_calories` | kcal, no conversion. Total burn, active and resting. |
| `activity.distance_m` | Leave empty | `equivalent_walking_distance` is not distance travelled. |
| `workouts.start`, `workouts.end`, `workouts.type` | `workout` `start_datetime`, `end_datetime`, `activity` | |
| `workouts.distance_m` | `workout` `distance` | "Distance traveled in meters". |
| `workouts.energy_kcal` | `workout` `calories` | kcal, as reported. |
| `workouts.avg_hr_bpm` | Leave empty | The workout document has no heart rate. |
| `fitness_markers.vo2max_ml_kg_min` | `vO2_max` `vo2_max` | Only new estimates from the person's own walking tests; skip the first, profile-based value. See below. |
| `mindfulness.mindful_min` | `session` with `type` `meditation`, `breathing` or `relaxation` | Sum of `end_datetime` minus `start_datetime` per day. |

## Getting the data out

### Oura API v2 (best for a repeatable script)

V2 is the only API; "The previous V1 API has been sunset" ([API docs](https://cloud.ouraring.com/v2/docs)). Base URL `https://api.ouraring.com`. Every request needs `Authorization: Bearer <token>` and a `User-Agent` header naming the app, e.g. `User-Agent: dotlife-sync/1.0`; requests without one "may be rejected" ([API docs](https://cloud.ouraring.com/v2/docs)).

**Personal access tokens are gone.** The docs say "personal access tokens were deprecated in December 2025 and are no longer available for use" ([API docs](https://cloud.ouraring.com/v2/docs), from its [OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)); the authentication page lists them only as "Personal Access Tokens [Deprecated]" ([Authentication](https://cloud.ouraring.com/docs/authentication)). Older guides and tools that ask for a personal token are out of date. Use OAuth2:

1. Create an API application. Oura's help centre points to the newer portal at [developer.ouraring.com](https://developer.ouraring.com); the older page at `cloud.ouraring.com/oauth/applications` still works for editing existing apps ([The Oura API](https://support.ouraring.com/hc/en-us/articles/4415266939155-The-Oura-API)). An app is limited to 10 users before Oura must approve it, which is plenty for one person ([API docs](https://cloud.ouraring.com/v2/docs)).
2. Run the server-side (authorisation code) flow: send the person to `https://cloud.ouraring.com/oauth/authorize` with `response_type=code`, then exchange the code at `https://api.ouraring.com/oauth/token` with `grant_type=authorization_code`. PKCE with `S256` is recommended. The `redirect_uri` must match a registered one exactly ([Authentication](https://cloud.ouraring.com/docs/authentication)).
3. Renew with `grant_type=refresh_token`. Each refresh token is single-use and each refresh returns a new one, so store the newest. The client-side (implicit) flow has no refresh token and its tokens last 30 days ([Authentication](https://cloud.ouraring.com/docs/authentication)). Oura's own pages disagree on server-side lifetime ("typically 24 hours" in one place, "typically last 30 days" in another) ([API docs](https://cloud.ouraring.com/v2/docs)); trust the `expires_in` in the token response.

Scopes: `email`, `personal`, `daily`, `heartrate`, `workout`, `tag`, `session`, `spo2` ([Authentication](https://cloud.ouraring.com/docs/authentication)). The OpenAPI spec also lists `heart_health` ("Heart health data") ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)) without saying which endpoints need it; it plausibly covers VO2 max and cardiovascular age, but that is unverified. Leaving out `scope` requests all scopes ([Authentication](https://cloud.ouraring.com/docs/authentication)). The person must also consent to each data type ([API docs](https://cloud.ouraring.com/v2/docs)).

Endpoints, all `GET` under `/v2/usercollection/` ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)):

| Data | Endpoint | Used for |
| --- | --- | --- |
| Sleep periods | `sleep` | Sleep, heart, breathing, temperature |
| Daily sleep score | `daily_sleep` | Not in the format |
| Daily readiness | `daily_readiness` | Temperature (alternative) |
| Daily activity | `daily_activity` | Activity |
| Workouts | `workout` | Workouts |
| Sessions | `session` | Mindfulness |
| Daily SpO2 | `daily_spo2` | SpO2 |
| VO2 max | `vO2_max` (capital O) | Fitness markers |
| Heart rate samples | `heartrate` | Not needed |
| Others | `daily_stress`, `daily_resilience`, `daily_cardiovascular_age`, `enhanced_tag`, `tag` (deprecated), `sleep_time`, `rest_mode_period`, `ring_configuration`, `ring_battery_level`, `personal_info` | Not in the format |

Most endpoints take `start_date` and `end_date` (`YYYY-MM-DD`) and `next_token`; `heartrate` takes `start_datetime` and `end_datetime`. Follow `next_token` until it is null ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). Dates "are interpreted in the user's local timezone" ([API docs](https://cloud.ouraring.com/v2/docs)). The docs don't say whether `end_date` is inclusive, so ask for a day more than you need and drop extras. For backfills Oura suggests "1-3 months at a time" ([API docs](https://cloud.ouraring.com/v2/docs)). There is also a `/v2/sandbox/usercollection/` copy of each endpoint with fake data for testing a script ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)).

Rate limits: the FAQ says "5000 requests per 5-minute period"; a `429` comes with `Retry-After` and `X-RateLimit-*` headers, and limits apply per token and per app ([API docs](https://cloud.ouraring.com/v2/docs)). A daily sync uses a handful of requests. Oura recommends webhooks, but they need a public server, which a local script doesn't have; polling once a day is fine.

**Membership.** "Gen3 and later users without active Oura Membership can't access their data through the Oura API" ([The Oura API](https://support.ouraring.com/hc/en-us/articles/4415266939155-The-Oura-API)). A `403` can mean the subscription has expired ([API docs](https://cloud.ouraring.com/v2/docs)). Without a membership, use the export below.

**AI use.** Oura's API agreement (effective 8 June 2026) says that anyone using Oura data "in connection with a large language model" may do so "solely through the MCP Server", and forbids using the API to "prompt, or otherwise provide input" to an AI model ([API Agreement](https://cloud.ouraring.com/legal/api-agreement), section 4(d)). It has no exception for people fetching their own data. So the sync script should write API responses straight to the CSV files without passing them through the AI agent, and the person should read the agreement and decide for themselves. This guide is not legal advice.

### Data export from the Membership Hub (one-off, any membership)

Available "with or without active membership" ([Export & Share Your Oura Data](https://support.ouraring.com/hc/en-us/articles/360025441594)):

1. Log in at [membership.ouraring.com](https://membership.ouraring.com).
2. Select "Export data", then "Request your data".
3. Wait: exports "can take up to 10 days". Oura emails when it is ready.
4. Return to the Membership Hub and download the export.

Durations in the export are in seconds, and its data models are the ones described in the API v2 docs ([Export & Share Your Oura Data](https://support.ouraring.com/hc/en-us/articles/360025441594)). Oura does not document the file names or format (CSV, JSON or archive); read them from an actual export before mapping. Expect the same field names as the API and map them as below. A community project says Oura retired an older web export of daily trends (one row per day, 54 columns) ([marktron/oura-sync](https://github.com/marktron/oura-sync), community); guides that describe it are out of date.

The app's "Shareable Reports" (menu, then "Reports", then "Shareable Reports") are PDF summaries with fixed time frames ([Export & Share Your Oura Data](https://support.ouraring.com/hc/en-us/articles/360025441594)). They are not machine-readable; don't transcribe from them when the API or export has the data.

### Connectors in AI tools

The API agreement defines an "MCP Server" that Oura operates to give AI tools controlled access to user data ([API Agreement](https://cloud.ouraring.com/legal/api-agreement)), but no public address, setup page or listing for it was found on Oura's developer portal, API docs or help centre. Unverified: whether it is available to individual members. Many community MCP servers wrap the API; they are not from Oura, and the agreement's AI clause applies to them. Since the API can be scripted, a connector is not needed for dotlife.

## Mapping to the format

**Oura's `day` field.** Every document has a `day` (`YYYY-MM-DD`), "Day that the sleep belongs to" for sleep, and the like for others ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). Oura's sleep day turns over at 6 pm: a `late_nap` is a nap that "ended after sleep day change (6 pm), contributes to next days daily scores" ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json); see also [Nap Detection](https://support.ouraring.com/hc/articles/1500009653181)). So a night's `day` is normally the morning you woke up, which matches dotlife. Still compute `date` yourself as the local date of `bedtime_end` in the `config.toml` time zone, which is dotlife's rule, and use `day` only as a cross-check.

**`sleep` versus `daily_sleep`.** `sleep` returns one document per sleep period, and "A user can have multiple sleep periods per day" ([API docs](https://cloud.ouraring.com/v2/docs)). These hold the stage durations, heart rate, HRV, breathing and a nested `readiness` object. `daily_sleep` has one document per day with only the sleep `score` and its `contributors` ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)), so it fills nothing in dotlife.

**Picking the long sleep.** `type` is one of ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)):

- `long_sleep`: "sleep that is long enough (>3h) to automatically contribute to daily scores". This is the night.
- `sleep`: a confirmed nap or sleep of 15 minutes to 3 hours.
- `late_nap`: a confirmed nap that ended after 6 pm.
- `rest`: "Falsely detected sleep / nap, rejected in confirm prompt by user". Skip.
- `deleted`: deleted by the person. Skip.

Write one `sleep.csv` row per `long_sleep`, `sleep` or `late_nap` period; the dashboard treats the longest session of a date as the main one, so naps don't replace the night. If a date has two `long_sleep` periods (a broken night), write both. Take heart, HRV, breathing and temperature from the longest `long_sleep` of each wake date only, never from a nap. If a date has no `long_sleep`, leave those columns empty for it.

**Resting heart rate: use `average_heart_rate`.** Oura defines Average RHR as "Your average RHR captured during the night" and Lowest RHR as "Your lowest RHR value captured during the night" ([Resting Heart Rate](https://support.ouraring.com/hc/en-us/articles/360025588793)). The lowest value is a single minimum, the extreme of the night; the average describes the whole night at rest, so it is the steadier figure and the closer match to a daily resting heart rate from other sources. Note the API's value is computed from 30-second samples, while the app shows the mean of 5-minute samples, so it can differ slightly from the app ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). Keep `lowest_heart_rate` as a custom metric if the person wants it.

**HRV.** `average_hrv` is the night's average; Oura measures HRV only during sleep, in five-minute samples, in milliseconds ([Heart Rate Variability](https://support.ouraring.com/hc/en-us/articles/360025441974)). Neither that page, the [Glossary](https://support.ouraring.com/hc/en-us/articles/5949130374547-Glossary) nor the API spec names the HRV method. Oura has no other HRV value, so FORMAT.md allows it; record in `sources.md` that Oura's method is not documented.

**Temperature.** `temperature_deviation` is "Temperature deviation in degrees Celsius" ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)): the night's skin temperature against the person's baseline, with 0.0 as their long-term average ([Body Temperature](https://support.ouraring.com/hc/en-us/articles/360025587493)). That is exactly `skin_temp_delta_c`. The API has no absolute skin temperature, so leave `skin_temp_c` empty. Don't use `temperature_trend_deviation`, which is a weighted three-day average. The baseline is set over the first couple of weeks of wear and again after a ring change ([Body Temperature](https://support.ouraring.com/hc/en-us/articles/360025587493)), so early values are less settled; they are still real readings.

**SpO2.** Measured during sleeps longer than three hours, on Gen3 and later only ([Blood Oxygen Sensing](https://support.ouraring.com/hc/en-us/articles/7328398760851-Blood-Oxygen-Sensing-SpO2)). File `daily_spo2` under its `day`, which should be the wake date of that night's long sleep. If `spo2_percentage` is null, leave the cell empty.

**Activity.** `daily_activity` is "a 24-hour period starting at 4 a.m." ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json); "Every day, Oura begins calculating your total burn at 4 AM", [How Oura Measures Steps & Activity](https://support.ouraring.com/hc/en-us/articles/360025576833)). That is a source's own day: follow [Days, weeks and months in FORMAT.md](../../FORMAT.md#days-weeks-and-months) and file each document under its `day`, without splitting it. `total_calories` is Oura's total burn, "whether active or resting" ([Glossary](https://support.ouraring.com/hc/en-us/articles/5949130374547-Glossary)), which is what `energy_kcal` wants. Leave `distance_m` empty: equivalent walking distance is "an estimate of the walking distance equal to your daily calorie burn", "not the actual mileage traveled" ([How Oura Measures Steps & Activity](https://support.ouraring.com/hc/en-us/articles/360025576833)). The current day's document keeps changing until the day ends; re-fetch it.

**Active minutes.** Oura's own measure is activity time, "a measure of your activity-based movement throughout the day". Movement counts only if it was imported from a third-party integration, tracked manually, or confirmed through Automatic Activity Detection, and the app shows no activity time on a day with no activities ([How Oura Measures Steps & Activity](https://support.ouraring.com/hc/en-us/articles/360025576833)). Activity time replaced walking equivalency on 21 May 2025 for Gen3 and Oura Ring 4, and isn't applied to earlier days (same page). The API has no daily activity-time field, so add up the durations (`end_datetime` minus `start_datetime`) of each day's `workout` documents, by the local date of `start_datetime`, in minutes. Unverified: whether a workout with `source` `autodetected` is one the person has not yet confirmed (the spec lists it beside `confirmed` without saying); check a few days against the app before counting those. Leave `active_min` empty on a day with no workouts, as the app shows none, and name the measure ("Oura activity time, from workouts") in `sources.md`. The `daily_activity` fields `low_activity_time`, `medium_activity_time` and `high_activity_time` are seconds spent at each intensity ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)), not activity time; they are listed under "Not in the format".

**Workouts.** One row per `workout`, `date` from the local date of `start_datetime`. `type` is `activity` as given (e.g. `walking`). Leave `distance_m` and `energy_kcal` empty when null.

**VO2 max.** The `vO2_max` document has `day`, `timestamp` and `vo2_max` ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). Oura calls it Cardio Capacity, in ml/kg/min, on Gen3 and later with a membership. The first value comes from the person's profile details and is "an estimate only, based on population averages"; a brisk walking test (about monthly) or a value the person enters by hand updates it ([Cardio Capacity](https://support.ouraring.com/hc/en-us/articles/28336620578835-Cardio-Capacity-VO2-Max)). The format keeps only estimates based on the person's own workouts, so skip that first value. The API doesn't flag it, so skip the earliest `vO2_max` document unless the person says it came from a walking test. A value entered by hand comes from elsewhere (a lab or another device); keep it only if `sources.md` says so. After that, write a row only for a document with a new `timestamp` and a value that differs from the last one written.

**Mindfulness.** `session` `type` is one of `breathing`, `meditation`, `nap`, `relaxation`, `rest`, `body_status` ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). Count `meditation`, `breathing` and `relaxation`; skip the rest (naps already show up as sleep). Sum the durations per local date of `start_datetime`, in minutes. Days with no session are not gaps; don't write `0`.

**Cycle.** Leave `cycle.csv` to another source. The API has no cycle endpoint ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). Cycle Insights periods are logged by hand in the app, and the only export Oura describes is a six-month shareable report ([Cycle Insights](https://support.ouraring.com/hc/en-us/articles/4410663885331)). Whether the Membership Hub export includes logged periods is unverified; if it does, write a row for each logged period day, with `flow_level` only when a flow amount is recorded and empty otherwise, never from predictions. Oura's temperature is skin temperature, "not the same as basal, or core body temperature" ([Body Temperature](https://support.ouraring.com/hc/en-us/articles/360025587493)), and a deviation, so it can't fill `bbt_c`.

**Timestamps and units.** API timestamps are ISO 8601 with a UTC offset ([API docs](https://cloud.ouraring.com/v2/docs)); keep the offset, drop the milliseconds. Durations are in seconds unless stated ([API docs](https://cloud.ouraring.com/v2/docs)); round minutes to whole numbers.

**Source.** Write `oura`.

Example rows (made up, for Alice):

```csv
date,start,end,source,asleep_min,deep_min,rem_min,light_min,awake_min
2026-03-08,2026-03-07T23:12+01:00,2026-03-08T07:05+01:00,oura,431,74,96,261,42
```

```csv
date,source,resting_hr_bpm,hrv_ms
2026-03-08,oura,56,48
```

## Watch out for

- **Sync lag.** Sleep and readiness only arrive after the person opens the Oura app; activity, stress and heart rate sync in the background ([API docs](https://cloud.ouraring.com/v2/docs)). Re-fetch the last few days on every sync and stage them with `window=(first, last)`, which replaces Oura's rows for those dates.
- **Edited sleep.** Bedtime edits and reanalysis change a period (`sleep_analysis_reason` = `bedtime_edit` etc.) ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)). The `start` may have moved, so replace by date: staging a window replaces every row of those dates, and the old one goes.
- **4 am activity day.** Steps taken between midnight and 4 am land on the previous `day` (see [FORMAT.md](../../FORMAT.md#days-weeks-and-months) on a source's own day). Daily totals won't match a watch that resets at midnight.
- **Non-wear.** `daily_activity` has `non_wear_time` (seconds) and `class_5_min` uses `0` for non-wear. A day mostly off the finger still gets a document with low steps; keep the real values and let dotlife's watch-off rule handle it.
- **Duplicate workouts.** `workout` `source` can be `manual`, `autodetected`, `confirmed`, `workout_heart_rate`, `live_third_party_heart_rate` or `live_oura_heart_rate` ([OpenAPI spec](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)), so some workouts are typed in by hand or recorded with another device. If the same session also comes from a watch, keep the source ranked higher in `sources.md`.
- **Hardware.** SpO2, VO2 max and API access depend on Gen3 or later and a membership; on Gen2, leave those columns empty.
- **Repeated VO2 max.** Keep only new estimates (see above); `stale_after_days` in `config.toml` flags a value that stops changing.
- **Old tutorials.** Anything using v1 endpoints or personal access tokens no longer works.

## Not in the format

- Sleep score (`daily_sleep` `score`) and its contributors.
- Readiness score (`daily_readiness` `score`) and its contributors.
- Activity score, targets and inactivity alerts (`daily_activity`).
- Lowest heart rate during sleep (`sleep` `lowest_heart_rate`).
- Sleep efficiency, latency (seconds) and time in bed (`sleep` `efficiency`, `latency`, `time_in_bed`).
- Temperature trend deviation (`temperature_trend_deviation`).
- Height and weight in `personal_info`: profile values whose units the spec doesn't give. Leave `body.height_cm` empty unless the person confirms the unit and the value is a new measurement.
- Breathing disturbance index (`daily_spo2` `breathing_disturbance_index`).
- Daily stress and recovery time in seconds (`daily_stress` `stress_high`, `recovery_high`) and resilience level (`daily_resilience`).
- Cardiovascular age and pulse wave velocity (`daily_cardiovascular_age` `vascular_age`, `pulse_wave_velocity`).
- MET minutes, resting time and low, medium and high activity time (`daily_activity`).
- Heart rate samples every 5 minutes (`heartrate`).
- Enhanced tags (`enhanced_tag`): lifestyle, habit and mood tags with start and end times.
- Workout intensity and label (`workout` `intensity`, `label`) and session mood (`session` `mood`).
- Recommended bedtime window (`sleep_time`) and rest mode periods (`rest_mode_period`).

## Sources

- [Oura API Documentation (v2)](https://cloud.ouraring.com/v2/docs)
- [Oura API OpenAPI spec 1.43](https://cloud.ouraring.com/v2/static/json/openapi-1.43.json)
- [Oura API: Authentication](https://cloud.ouraring.com/docs/authentication)
- [Oura API Agreement](https://cloud.ouraring.com/legal/api-agreement)
- [Oura Developer Portal](https://developer.ouraring.com)
- [Oura Member Care: The Oura API](https://support.ouraring.com/hc/en-us/articles/4415266939155-The-Oura-API)
- [Oura Member Care: Export & Share Your Oura Data](https://support.ouraring.com/hc/en-us/articles/360025441594)
- [Oura Member Care: Resting Heart Rate](https://support.ouraring.com/hc/en-us/articles/360025588793)
- [Oura Member Care: Heart Rate Variability](https://support.ouraring.com/hc/en-us/articles/360025441974)
- [Oura Member Care: Body Temperature](https://support.ouraring.com/hc/en-us/articles/360025587493)
- [Oura Member Care: Blood Oxygen Sensing (SpO2)](https://support.ouraring.com/hc/en-us/articles/7328398760851-Blood-Oxygen-Sensing-SpO2)
- [Oura Member Care: How Oura Measures Steps & Activity](https://support.ouraring.com/hc/en-us/articles/360025576833)
- [Oura Member Care: Glossary](https://support.ouraring.com/hc/en-us/articles/5949130374547-Glossary)
- [Oura Member Care: Nap Detection](https://support.ouraring.com/hc/articles/1500009653181)
- [Oura Member Care: Cardio Capacity (VO2 Max)](https://support.ouraring.com/hc/en-us/articles/28336620578835-Cardio-Capacity-VO2-Max)
- [Oura Member Care: Cycle Insights](https://support.ouraring.com/hc/en-us/articles/4410663885331)
- [marktron/oura-sync](https://github.com/marktron/oura-sync) (community)

Checked 2026-10-29.
