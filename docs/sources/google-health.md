# Google Health (formerly Fitbit)

Google Health is Google's health app and data platform for Fitbit trackers, Pixel Watch and connected apps. On 19 May 2026 the Fitbit app became the Google Health app and Fitbit Premium became Google Health Premium, and the Fitbit Web API is now called the Google Health API ([Fitbit to Google Health changes](https://support.google.com/googlehealth/answer/17068213?hl=en), [About the Google Health API](https://developers.google.com/health/about)). It can fill `activity.csv`, `workouts.csv`, `sleep.csv` (with stages), `heart.csv`, `body.csv`, `fitness_markers.csv`, `vitals.csv` (SpO2, respiratory rate, skin temperature and its change), `nutrition.csv` and `glucose.csv`. It cannot fill `cycle.csv` or `mindfulness.csv` through the API (see below).

## What it fills

Data type names, field names and units are from the Google Health API v4 ([Data types](https://developers.google.com/health/data-types), [discovery document](https://health.googleapis.com/$discovery/rest?version=v4)). Many numbers arrive as JSON strings (for example `"countSum": "8421"`); parse them.

| dotlife column | From | Notes |
| --- | --- | --- |
| `activity.steps` | `steps` daily roll-up, `countSum` | One value per day from `dailyRollUp`. |
| `activity.distance_m` | `distance` daily roll-up, `millimetersSum` | Millimetres; divide by 1,000. |
| `activity.floors` | `floors` daily roll-up, `countSum` | |
| `activity.active_min` | `active-minutes` daily roll-up, `activeMinutesRollupByActivityLevel[].activeMinutesSum` where `activityLevel` is `MODERATE` or `VIGOROUS` | Google's own "active minutes" are "10 minutes or more of continuous moderate-to-intense activity" ([Track Active Zone Minutes or active minutes](https://support.google.com/googlehealth/answer/14236509?hl=en)). The API splits minutes into `LIGHT`, `MODERATE` and `VIGOROUS` ([discovery document](https://health.googleapis.com/$discovery/rest?version=v4)); sum the last two. Name the measure ("Google Health active minutes, moderate + vigorous") in `sources.md`. See below on Active Zone Minutes. |
| `activity.sedentary_min` | `sedentary-period` daily roll-up, `durationSum` | A duration string such as `"30600s"`; divide the seconds by 60. |
| `activity.energy_kcal` | `total-calories` daily roll-up, `kcalSum` | Total energy burned, active plus resting, as the format wants. Don't use `active-energy-burned`, which is active energy only. |
| `workouts.start`, `workouts.end` | `exercise` `interval.startTime`, `endTime` plus `startUtcOffset`, `endUtcOffset` | UTC times with the local offset as seconds, e.g. `"7200s"`. |
| `workouts.type` | `exercise` `exerciseType` | An enum such as `RUNNING`, `WALKING`, `YOGA`; write it in lower case. |
| `workouts.avg_hr_bpm` | `metricsSummary.averageHeartRateBeatsPerMinute` | |
| `workouts.distance_m` | `metricsSummary.distanceMillimeters` | Divide by 1,000. |
| `workouts.energy_kcal` | `metricsSummary.caloriesKcal` | As reported. |
| `sleep.start`, `sleep.end` | `sleep` `interval.startTime`, `endTime` plus offsets | One row per session, naps included. |
| `sleep.asleep_min` | `summary.minutesAsleep` | For staged sleep this is light + REM + deep, excluding awake. |
| `sleep.deep_min`, `sleep.rem_min`, `sleep.light_min` | `summary.stagesSummary[]` where `type` is `DEEP`, `REM`, `LIGHT`: `minutes` | Only when `type` is `STAGES`. A `CLASSIC` sleep has `ASLEEP` and `RESTLESS` instead; leave these empty. |
| `sleep.awake_min` | `summary.minutesAwake` | Sum of `AWAKE` stages. |
| `heart.resting_hr_bpm` | `daily-resting-heart-rate` `beatsPerMinute` | Already one value per date. |
| `heart.hrv_ms` | `daily-heart-rate-variability` `averageHeartRateVariabilityMilliseconds` | RMSSD in ms, measured during sleep. |
| `body.weight_kg` | `weight` `weightGrams` | Grams; divide by 1,000. |
| `body.body_fat_pct` | `body-fat` `percentage` | |
| `body.height_cm` | `height` `heightMillimeters` | A sample type ([Data types](https://developers.google.com/health/data-types)); millimetres, so divide by 10. Write a row only on a day with a new sample. |
| `fitness_markers.vo2max_ml_kg_min` | `vo2-max` `vo2Max`, or `daily-vo2-max` `vo2Max` | ml/kg/min. The app's former Cardio Fitness Score is now called VO2 max. See "Record only new readings" below. |
| `vitals.spo2_pct` | `daily-oxygen-saturation` `averagePercentage` | The average during sleep. |
| `vitals.respiratory_rate_brpm` | `daily-respiratory-rate` `breathsPerMinute` | |
| `vitals.skin_temp_c` | `daily-sleep-temperature-derivations` `nightlyTemperatureCelsius` | "The mean of skin temperature samples taken from the user's sleep" ([discovery document](https://health.googleapis.com/$discovery/rest?version=v4)). |
| `vitals.skin_temp_delta_c` | `daily-sleep-temperature-derivations`: `nightlyTemperatureCelsius` minus `baselineTemperatureCelsius` | No delta field is sent; Google's guide computes it this way. The baseline is Google's own, "the median of the user's nightly skin temperature over the past 30 days" ([discovery document](https://health.googleapis.com/$discovery/rest?version=v4)), so the difference is a change from the source's baseline, as the format asks. Leave empty when the baseline is missing. |
| `nutrition.energy_in_kcal` | `nutrition-log` daily roll-up, `energy.kcalSum` | Only food the person logged. |
| `nutrition.carbs_g`, `nutrition.fat_g` | `nutrition-log` roll-up `totalCarbohydrate.gramsSum`, `totalFat.gramsSum` | |
| `nutrition.protein_g` | `nutrition-log` roll-up `nutrients[]` where `nutrient` is `PROTEIN`: `quantity.gramsSum` | |
| `nutrition.caffeine_mg` | `nutrients[]` where `nutrient` is `CAFFEINE`: `quantity.gramsSum` | Grams; multiply by 1,000. |
| `nutrition.water_ml` | `hydration-log` daily roll-up, `amountConsumed.millilitersSum` | Already in ml whatever unit was logged. |
| `glucose.glucose_mean_mmol_l` | `blood-glucose` daily roll-up, `bloodGlucoseMilligramsPerDeciliterAvg` | mg/dL; divide by 18.016. Sensitive category: ask before switching it on. |
| `glucose.time_in_range_pct` | `blood-glucose` readings, `bloodGlucoseMilligramsPerDeciliter` | No time-in-range field. Work it out per local day as the share of readings from 70 to 180 mg/dL (3.9 to 10.0 mmol/L), the range in FORMAT.md. Only from a continuous glucose monitor (CGM); leave it empty for finger-prick readings, as FORMAT.md says. |

Left empty: `vitals.systolic_mmhg` and `vitals.diastolic_mmhg` (no blood pressure data type in the [data types list](https://developers.google.com/health/data-types)), `nutrition.alcohol_drinks` and `body.waist_cm` (no matching field). `cycle.csv` and `mindfulness.csv` can't be read from the API; see "Not in the format".

## Getting the data out

### 1. Google Health API with your own Google Cloud project (best for a repeatable script)

The Google Health API is the only supported web API. The legacy Fitbit Web API's support ended on 30 September 2026 and its endpoints are being turned off: Google's migration guide says 2 November 2026, after which calls return HTTP 410 ([Migration guide](https://developers.google.com/health/migration), [About](https://developers.google.com/health/about)); the banner on the old Fitbit developer site says 30 October 2026 ([Fitbit Web API application design](https://dev.fitbit.com/build/reference/web-api/developer-guide/application-design/)). Either way, don't build on `api.fitbit.com`. Its "Personal", "Server" and "Client" app types, the 150 requests per user per hour limit and Fitbit OAuth tokens belong to that old API ([same page](https://dev.fitbit.com/build/reference/web-api/developer-guide/application-design/)); old tokens cannot be carried over ([Migration guide](https://developers.google.com/health/migration)).

What it needs ([Set up](https://developers.google.com/health/setup)):

- A Google Account linked to the Google Health app. Fitbit logins had to move to a Google Account ([Fitbit to Google Health changes](https://support.google.com/googlehealth/answer/17068213?hl=en)); an unlinked account gets `400 ACCOUNT_NOT_LINKED` ([Migration guide](https://developers.google.com/health/migration)).
- A Google Cloud project with the Google Health API enabled and an OAuth 2.0 client ID. Google's setup page uses the "Web Server" client type with `https://www.google.com` as redirect URI; Google's CLI (below) uses a "Desktop application" client instead ([google-health-cli README](https://github.com/Google-Health-API/google-health-cli)).
- The OAuth consent screen in "Testing" with user type "External", and the person's own address added as a test user. An unverified client is capped at 100 users, so a one-person app needs no review; going past 100 users needs a third-party security review ([Set up](https://developers.google.com/health/setup)).
- In Testing, refresh tokens expire after 7 days, so the person must sign in again about weekly. Production refresh tokens generally last until revoked or unused for about six months ([Set up](https://developers.google.com/health/setup)).

There are no app types in the new API, and no separate intraday approval: intraday data comes from the same endpoints ([About](https://developers.google.com/health/about)).

OAuth scopes (read-only is enough; [Scopes](https://developers.google.com/health/scopes)):

- `https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly`: steps, distance, floors, active minutes, sedentary periods, calories, exercise, VO2 max.
- `https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly`: resting heart rate, HRV, SpO2, respiratory rate, skin temperature, weight, body fat, height, blood glucose.
- `https://www.googleapis.com/auth/googlehealth.sleep.readonly`: sleep.
- `https://www.googleapis.com/auth/googlehealth.nutrition.readonly`: nutrition and hydration logs.

Which data type needs which scope is listed on [Data types](https://developers.google.com/health/data-types). Request only the ones for categories switched on in `config.toml`.

Endpoints ([Endpoints](https://developers.google.com/health/endpoints)). The base URL is `https://health.googleapis.com/v4`; data type names are kebab case in paths and snake case in filters.

- `GET /users/me/dataTypes/{type}/dataPoints`: raw records, not deduplicated.
- `GET /users/me/dataTypes/{type}/dataPoints:reconcile`: records with overlaps from several devices and syncs resolved. Use this for sleep, exercise and the daily types.
- `POST /users/me/dataTypes/{type}/dataPoints:dailyRollUp`: one aggregate per local (civil) day. Body: `{"range": {"start": {"date": {...}}, "end": {"date": {...}}}, "windowSizeDays": 1}`. The end is exclusive. Use this for steps, distance, floors, active minutes, sedentary time, total calories, weight, body fat, nutrition, hydration and glucose. Height, which has no roll-up, is read with `list` ([Data types](https://developers.google.com/health/data-types)).
- `GET /users/me/identity` and `GET /users/me/pairedDevices`: account ID, and each device with its `lastSyncTime`.
- `GET .../exercise/dataPoints/{id}:exportExerciseTcx`: one workout as TCX, which needs the `location.readonly` scope as well ([REST reference](https://developers.google.com/health/reference/rest)).

Filters ([Filters](https://developers.google.com/health/filters)) take `>=` and `<` joined by `AND`, URL-encoded, for example:

```text
sleep.interval.civil_end_time >= "2026-03-04T00:00:00" AND sleep.interval.civil_end_time < "2026-03-11T00:00:00"
exercise.interval.civil_start_time >= "2026-03-01" AND exercise.interval.civil_start_time < "2026-03-08"
daily_resting_heart_rate.date >= "2026-03-01"
```

The same page says sleep filters on the end time and exercise on the start time, which matches dotlife's rules.

Limits:

- Pages hold up to 10,000 points, but only 25 for `sleep` and `exercise`; follow `nextPageToken` ([Endpoints](https://developers.google.com/health/endpoints)). `dailyRollUp` returns 90 points by default ([discovery document](https://health.googleapis.com/$discovery/rest?version=v4)).
- A roll-up range can span at most 14 days for `heart-rate`, `active-minutes`, `total-calories` and `calories-in-heart-rate-zone`, and 90 days for the rest ([Endpoints](https://developers.google.com/health/endpoints)). Backfill in chunks.
- 300 requests per user per minute; an unverified app gets 2.5 requests per second per user. Over the limit you get `429 Too Many Requests`; back off and retry ([Rate limits](https://developers.google.com/health/rate-limits)).
- How far back history goes is not documented ([Data management](https://developers.google.com/health/data-management)); try the earliest date the person cares about and record what comes back.

### 2. Google Health CLI (`ghealth`)

Google Health released an open-source command-line tool for the Google Health API on 1 July 2026, "designed with agent use in mind" ([9to5Google](https://9to5google.com/2026/07/01/google-health-cli/)). It lives in the `Google-Health-API` GitHub organisation, is written in Go and licensed Apache 2.0 ([README](https://github.com/Google-Health-API/google-health-cli)). It still needs the person's own Cloud project and OAuth client; `ghealth setup` walks through it and stores credentials in `~/.config/ghealth/`. Useful commands from the README:

```text
ghealth data steps daily-rollup --from 2026-03-22 --to 2026-03-29 --format csv
ghealth schema types
```

`--format csv` flattens nested fields into dot-separated columns, `--raw` gives the unmodified API response, and days missing from roll-up output mean no data, not zero. It ships two agent skills (`ghealth`, `ghealth-shared`). A sync script can call it instead of handling OAuth itself; the API rules above still apply.

### 3. Google Takeout (one-off archive, good for backfill)

People who sign in with a Google Account export everything with Google Takeout, selecting Google Health ([How do I export my Google Health data?](https://support.google.com/googlehealth/answer/14236615?hl=en), [Google Health blog post](https://blog.google/products-and-platforms/products/google-health/connect-data-across-devices/)). The help page says it covers activity, exercise, sleep and heart rate data. Accounts still on a Fitbit login used Settings > Data Export on the Fitbit settings page; after 19 May 2026 Fitbit logins no longer give access, and Google began deleting unmigrated data on 15 July 2026 ([same page](https://support.google.com/googlehealth/answer/14236615?hl=en), [Fitbit to Google Health changes](https://support.google.com/googlehealth/answer/17068213?hl=en)).

Unverified: Google does not document the archive's folder names or file formats. Community reports describe a folder per data type with JSON and CSV files, a `Physical Activity` folder and very many files ([Garmin forum thread](https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-web/391568/export-from-fitbit-using-google-take-out-and-import-to-garmin/1859509)), and one user got an archive with only `archive_browser.html` ([Fitbit community](https://community.fitbit.com/t5/iOS-App/Failed-data-export/m-p/5831841)). Before writing an import, list the person's archive and map the files they actually have; don't assume names. Takeout is a snapshot and doesn't update, so use the API for ongoing sync.

A single GPS workout can be exported as TCX from the app: Fitness tab, tap the activity, More, Export ([How do I export my Google Health data?](https://support.google.com/googlehealth/answer/14236615?hl=en)).

### 4. Health Connect (Android, on the phone only)

Health Connect is a database stored on the Android device; Google doesn't keep it in the cloud ([Learn about Health Connect](https://support.google.com/android/answer/13770320?hl=en)). Apps reach it through the Android SDK, and there is no web API ([Health Connect for developers](https://developer.android.com/health-and-fitness/health-connect)), so a script on a computer can't read it. The Google Health app can write steps, VO2 max, exercise, sleep stages, skin temperature, blood glucose, heart rate, HRV, respiratory rate, resting heart rate, weight, body fat, nutrition, hydration and periods to it, and reads more, including SpO2 and mindfulness sessions ([Use Health Connect with Google Health](https://support.google.com/googlehealth/answer/14506680?hl=en)). On Android 14 and later it can make a scheduled daily, weekly or monthly export, `Health Connect.zip`, to a cloud storage app, via Settings > search "Health Connect" > Manage data > Backup and restore > Scheduled export; the ZIP's contents are not documented ([Back up and restore your Health Connect data](https://support.google.com/android/answer/15323271?hl=en)). Use Health Connect only if the person already has an Android app that exports it to files.

### 5. Connectors for AI tools

No official Google Health MCP server or connector was found. Google's offer for agents is the CLI and its skills above. Several community MCP servers for the Google Health API exist ([Glama listing](https://glama.ai/mcp/servers/BerkKilicoglu/google-health-fitbit-mcp)); they are not affiliated with Google, and `sources.md` would have to name them before any data goes through them. Prefer a script.

## Mapping to the format

- **Source.** Write `google-health`. If the person only wants wearable readings, pass `dataSourceFamily=users/me/dataSourceFamilies/google-wearables` (excludes manual and phone-estimated data); the default `all-sources` includes data other apps synced in, and `google-sources` covers Google and Fitbit devices, Health Connect and manual entries ([Endpoints](https://developers.google.com/health/endpoints)). If another source in `sources.md` (for example a scale) also writes into Google Health, either filter it out here or leave that metric to the higher-ranked source, so the same reading isn't counted twice.
- **Dates.** Daily types carry a `date` "in the user's timezone" ([discovery document](https://health.googleapis.com/$discovery/rest?version=v4)); `dailyRollUp` buckets by civil (local) day ([Endpoints](https://developers.google.com/health/endpoints)). Use those dates as they are.
- **Timestamps.** Build `start` and `end` from the UTC time plus its offset: `startTime` `2026-03-08T06:30:00Z` with `startUtcOffset` `"3600s"` is `2026-03-08T07:30+01:00`.
- **Sleep.** File each session under the local date of its end time (`interval.civilEndTime.date`). Skip sessions with `metadata.processed` false and fetch them again later; the stages may not be final. `metadata.mainSleep` marks the longest staged sleep of a day and `metadata.nap` marks naps; both get rows, since `sleep.csv` is one row per session.
- **Workouts.** File under the local start date. Write `type` in lower case (`running`). Skip fields the summary doesn't have.
- **Resting HR, HRV, SpO2, respiratory rate, skin temperature.** One daily point per date; write it straight in. `skin_temp_c` is `nightlyTemperatureCelsius`; `skin_temp_delta_c` is `nightlyTemperatureCelsius - baselineTemperatureCelsius`, rounded to two decimals (e.g. 34.12 - 33.95 = 0.17). That subtraction only reads Google's baseline; never build a baseline of your own.
- **Active minutes, not Active Zone Minutes.** The app leads with Active Zone Minutes, which count 1 per minute in the fat-burn zone and 2 per minute in the cardio and peak zones ([Track Active Zone Minutes or active minutes](https://support.google.com/googlehealth/answer/14236509?hl=en), [discovery document](https://health.googleapis.com/$discovery/rest?version=v4)). That makes them points, not time, so they don't fit `active_min`. Use active minutes (moderate plus vigorous) as in the table. Google doesn't say whether the API's per-level minutes apply the app's 10-minute rule, so the API total can differ from the app's figure; check a few days against the app.
- **Height.** Write `height_cm` only on a day with a new `height` sample; a profile value that never changes is not a new reading.
- **Weight and body fat.** The roll-up gives the day's average; a script that wants one reading can instead `list` the day's samples and take the last. Smart-scale readings win on any day they exist; scale points have `dataSource.device.formFactor` `SCALE`.
- **Record only new readings.** `daily-vo2-max` is a daily point, so the same value can repeat for weeks; it also has an `estimated` flag for when "the confidence has decreased sufficiently to consider the value an estimation" ([discovery document](https://health.googleapis.com/$discovery/rest?version=v4)). Prefer the `vo2-max` samples, which are dated measurements, and write the latest one per local date. If only the daily type has data, skip rows with `estimated` true and rows equal to the previous written value.
- **Missing stays missing.** A day absent from a roll-up means no data. Don't write `0` for it, and leave a whole `activity` row out when there are no steps, active minutes or calories for that day.

A made-up `sleep.csv` row for Alice:

```text
date,start,end,source,asleep_min,deep_min,rem_min,light_min,awake_min
2026-03-08,2026-03-07T23:12+01:00,2026-03-08T07:05+01:00,google-health,431,62,95,274,42
```

## Watch out for

- **Deadline.** Anything still on `api.fitbit.com` stops working by early November 2026. Old Fitbit tokens can't be reused; the person signs in again with Google ([Migration guide](https://developers.google.com/health/migration)).
- **Weekly re-login in Testing mode.** Testing-mode refresh tokens expire after 7 days ([Set up](https://developers.google.com/health/setup)). The sync should detect an expired token and ask the person to sign in, never write empty rows.
- **Duplicates.** Overlapping records from several devices are stored separately and `list` returns all of them; use `reconcile` or the roll-ups ([Data management](https://developers.google.com/health/data-management)).
- **Records change.** Stored timestamps can be edited later ([Data management](https://developers.google.com/health/data-management)). Re-fetch the last few days on each sync and stage them with `window=(first, last)`, which replaces those dates.
- **Time zones.** API times are UTC plus an offset recorded where the person was. dotlife files dates by the time zone in `config.toml`; when the person travels, Google's civil dates and dotlife's can differ by a day. Note it rather than shifting values.
- **Feature changes in 2026.** Estimated Oxygen Variation and minute-by-minute skin temperature were removed from the app; Cardio Fitness Score became VO2 max, now based on GPS runs ([Fitbit to Google Health changes](https://support.google.com/googlehealth/answer/17068213?hl=en)). Expect a break in VO2 max values around May 2026.
- **Not every device sends every metric.** Device support varies ([Device compatibility](https://developers.google.com/health/data-types/device-compatibility)); a missing metric is a gap, not a zero.
- **The API is still changing.** New data types arrive in `v4beta` first, such as `skin-temperature-sensors` in October 2026 ([Release notes](https://developers.google.com/health/release-notes)). Stick to `v4` for a stable script.

## Not in the format

- Cycle data: the API's `menstrual-period`, `ovulation-test`, `moods` and `symptoms` types are write-only, so they can't be read ([Women's health](https://developers.google.com/health/data-types/womens-health)). Periods reach Health Connect on Android, but that is on-device only.
- Mindfulness sessions: no readable Google Health API data type (Health Connect only).
- Active Zone Minutes (`active-zone-minutes`, by fat-burn, cardio and peak zone), and light-level active minutes.
- Time in heart rate zones and daily heart rate zones.
- Intraday heart rate, HRV, SpO2 and steps (per minute or second).
- Sleep extras: time to fall asleep, short awakenings, out-of-bed segments, respiratory rate per sleep stage.
- Basal and active energy separately, and altitude.
- Core body temperature, ECG and irregular rhythm notifications (separate scopes).
- HRV extras: deep-sleep RMSSD, entropy, non-REM heart rate.
- Cardio fitness level (`POOR` to `EXCELLENT`) alongside VO2 max.
- Sleep score, Readiness and Resilience (formerly Stress score) appear in the app but have no Google Health API data type in the [data types list](https://developers.google.com/health/data-types).
- Swim lengths and individual food items.

## Sources

- [Fitbit to Google Health: key changes (Google Health Help)](https://support.google.com/googlehealth/answer/17068213?hl=en)
- [Track Active Zone Minutes or active minutes on your Fitbit device and Pixel Watch (Google Health Help)](https://support.google.com/googlehealth/answer/14236509?hl=en)
- [About the Google Health API](https://developers.google.com/health/about)
- [Fitbit Web API migration guide](https://developers.google.com/health/migration)
- [Set up the Google Health API](https://developers.google.com/health/setup)
- [Google Health API scopes](https://developers.google.com/health/scopes)
- [Google Health API data types](https://developers.google.com/health/data-types)
- [Google Health API endpoints](https://developers.google.com/health/endpoints)
- [Google Health API filters](https://developers.google.com/health/filters)
- [Google Health API rate limits](https://developers.google.com/health/rate-limits)
- [Google Health API data management](https://developers.google.com/health/data-management)
- [Google Health API release notes](https://developers.google.com/health/release-notes)
- [Google Health API REST reference](https://developers.google.com/health/reference/rest)
- [Google Health API v4 discovery document](https://health.googleapis.com/$discovery/rest?version=v4)
- [Sleep data type](https://developers.google.com/health/data-types/sleep)
- [Vitals data types](https://developers.google.com/health/data-types/vitals)
- [Skin temperature data types](https://developers.google.com/health/data-types/skin-temperature)
- [Steps data type](https://developers.google.com/health/data-types/steps)
- [Women's health data types](https://developers.google.com/health/data-types/womens-health)
- [Device compatibility](https://developers.google.com/health/data-types/device-compatibility)
- [Fitbit Web API application design (legacy)](https://dev.fitbit.com/build/reference/web-api/developer-guide/application-design/)
- [Google Health CLI README](https://github.com/Google-Health-API/google-health-cli)
- [Google Health now offers a CLI (9to5Google)](https://9to5google.com/2026/07/01/google-health-cli/)
- [How do I export my Google Health data? (Google Health Help)](https://support.google.com/googlehealth/answer/14236615?hl=en)
- [Google Health brings your data into one place, on your terms (Google blog)](https://blog.google/products-and-platforms/products/google-health/connect-data-across-devices/)
- [How do I use Health Connect with the Google Health app? (Google Health Help)](https://support.google.com/googlehealth/answer/14506680?hl=en)
- [Learn about Health Connect (Android Help)](https://support.google.com/android/answer/13770320?hl=en)
- [Back up and restore your Health Connect data (Android Help)](https://support.google.com/android/answer/15323271?hl=en)
- [Health Connect (Android Developers)](https://developer.android.com/health-and-fitness/health-connect)
- [Export from Fitbit using Google Takeout (Garmin forum, community)](https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-web/391568/export-from-fitbit-using-google-take-out-and-import-to-garmin/1859509)
- [Failed data export (Fitbit community)](https://community.fitbit.com/t5/iOS-App/Failed-data-export/m-p/5831841)
- [Google Health Fitbit MCP (Glama listing, community)](https://glama.ai/mcp/servers/BerkKilicoglu/google-health-fitbit-mcp)

Checked 2026-10-29.
