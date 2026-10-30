# Weather (Open-Meteo)

Open-Meteo is a free weather API that needs no account or key for non-commercial use. A standard-library script can call it once a day to fill `weather.csv` (mean temperature, daylight and precipitation) for the place where the person lives. Meteostat is a station-based alternative, covered briefly below.

## What it fills

Daily variable names and units are from Open-Meteo's [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) and [Forecast API](https://open-meteo.com/en/docs) docs, and were checked against a live response on 2026-10-29 (`daily_units` gave `°C`, `s` and `mm`).

| dotlife column | From | Notes |
| --- | --- | --- |
| `weather.temp_mean_c` | `daily` `temperature_2m_mean` | °C, the default unit. Air temperature at 2 m. Daily values are "a simple 24 hour aggregation from hourly values" ([Forecast API](https://open-meteo.com/en/docs)). |
| `weather.daylight_h` | `daily` `daylight_duration` | Seconds ("Number of seconds of daylight per day"); divide by 3600. |
| `weather.precipitation_mm` | `daily` `precipitation_sum` | mm, the default unit. "Sum of daily precipitation (including rain, showers and snowfall)" ([Forecast API](https://open-meteo.com/en/docs)). |

## Getting the data out

### Open-Meteo Historical Weather API (best for a repeatable script)

One `GET` to `https://archive-api.open-meteo.com/v1/archive` returns every day in a range ([Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)). Parameters:

- `latitude`, `longitude`: the home location (see [Location](#location)).
- `start_date`, `end_date`: required, `yyyy-mm-dd`.
- `daily=temperature_2m_mean,daylight_duration,precipitation_sum`.
- `timezone`: the IANA name from `config.toml`, e.g. `Europe/Berlin`. The default is `GMT`, and daily values need a time zone ([Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)). Don't use `auto`, which "resolves the time zone from the coordinates" and could differ from the person's `timezone`.

The response is JSON with a `daily` object: a `time` array of dates and one array per variable, in the same order. A missing value is `null`.

How far back and how fresh ([Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)):

- Data goes back to 1940 (ERA5, about 25 km), 1950 (ERA5-Land, about 11 km) and 2017 (ECMWF IFS, 9 km).
- ERA5 and ERA5-Land update "Daily with 5 days delay"; ECMWF IFS updates "Every 6 hours with no delay".
- The default model, Best Match, "combines IFS HRES, ERA5 and ERA5-Land seamlessly". So the archive has recent days too: a request on 2026-10-29 returned values up to and including that day.
- For decades-long comparisons, the docs advise using only ERA5 or ERA5-Land (`models=era5` or `models=era5_land`) for consistency. Those come with the 5-day delay. For a personal dashboard, the default is fine; whichever is chosen, keep it, so the series doesn't change model partway.

No key is needed: the `apikey` parameter is "Only required to commercial use", with a `customer-` server prefix ([Forecast API](https://open-meteo.com/en/docs)). A whole backfill is one request, and a daily sync is one more.

### Open-Meteo Forecast API with `past_days` (alternative)

`https://api.open-meteo.com/v1/forecast` takes the same `daily` and `timezone` parameters, plus `past_days` (0 to 92) and `forecast_days` (0 to 16, default 7) ([Forecast API](https://open-meteo.com/en/docs)). Its past days are archived forecasts, not reanalysis. The Historical Weather API's own page points people here for "weather information from the previous day" ([Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)), but it can't reach back further than 92 days, and mixing the two APIs would mix two datasets in one column. Use the archive for both the backfill and the daily sync, and use this only if the archive is unavailable.

### Terms, limits and licence

- Free use is for non-commercial purposes only, under "10'000 API calls per day, 5'000 per hour and 600 per minute", and 300,000 a month ([Terms](https://open-meteo.com/en/terms)). A personal dashboard is far below that.
- The data is licensed CC BY 4.0. Credit is required: "You must give appropriate credit, provide a link to the licence, and indicate if changes were made", and Open-Meteo suggests the text "Weather data by Open-Meteo.com" linking to `https://open-meteo.com/` ([Licence](https://open-meteo.com/en/licence)). The underlying reanalysis comes from the Copernicus Climate Change Service and ECMWF under their own licences, listed on the same page. If the person shares a screenshot or chart, add that credit.
- The terms can change at any time, with changes tracked on GitHub ([Terms](https://open-meteo.com/en/terms)). No 2025-2026 changes to these limits were found.

### Meteostat (station-based alternative)

[Meteostat](https://dev.meteostat.net/) has observations from weather stations rather than a model grid. Two routes:

- Yearly gzip-compressed CSV files per station at `https://data.meteostat.net/daily/{year}/{station}.csv.gz` ([Daily data](https://dev.meteostat.net/data/timeseries/daily)). No key or sign-up is needed ([Time series](https://dev.meteostat.net/data/timeseries)). A station that has no daily data returns HTTP 404.
- A JSON API through RapidAPI, which needs a RapidAPI key and has "a hard limit of 500 requests per month" on the free plan ([JSON API](https://dev.meteostat.net/api)).

Data is CC BY 4.0, commercial use allowed, crediting "Meteostat and its meteorological data providers" ([Licence](https://dev.meteostat.net/license)). The script would also need to choose a nearby station. The daily docs page doesn't list column names, units or whether days are UTC or local, so check those on Meteostat's parameter pages before using it; that is unverified here. Meteostat has no daylight value that we could confirm, so `daylight_h` would stay empty or come from Open-Meteo.

A national weather service is another option, but each has its own API and terms; this guide doesn't cover them.

## Location

The script needs a latitude and longitude. Store them in `config.toml`:

```toml
[weather]
latitude = 52.52
longitude = 13.41
```

Round both to two decimals (about 1 km north-south). `config.toml` lives in the person's repo, so a precise home address shouldn't be there, and two decimals lose nothing: the finest model in the default mix is 9 km ([Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)), and the API snaps the request to a grid cell anyway (the response's `latitude` and `longitude` are the cell's, not the ones sent).

This guide uses one home location for every day. Weather is for where the person lives unless they choose to follow travel days. Following travel would need a location per day from somewhere else (e.g. `travel.csv` only has a country), so keep it simple and use one location.

## Mapping to the format

- **One row per local date.** Pass `timezone` equal to `config.toml`'s `timezone`; the `time` array then holds local dates, written as-is to `date`.
- **Units.** `temp_mean_c` = `temperature_2m_mean`. `daylight_h` = `daylight_duration / 3600`, rounded to two decimals. `precipitation_mm` = `precipitation_sum`. Ask for Celsius and mm explicitly or leave `temperature_unit` and `precipitation_unit` at their defaults; never set them to Fahrenheit or inch.
- **Source.** Write `open-meteo` in `source`.
- **Stop at yesterday.** The archive returns today with a partial, partly forecast value. Set `end_date` to yesterday in the local time zone.
- **Re-fetch a window.** Each run, fetch from 7 days before yesterday to yesterday and replace those dates' rows. The window covers late-arriving and revised data (see below) and makes a second run give the same file. On the first run, fetch from the start date the person wants in one request.
- **Missing stays missing.** A `null` becomes an empty cell. If a whole day is missing from the response, leave the day out; don't copy a neighbouring day or average around it. The validator reports the gap.

A row looks like this (made-up values):

```csv
date,source,temp_mean_c,daylight_h,precipitation_mm
2026-03-03,open-meteo,5.9,10.71,0
```

The script goes in `config.toml` as a `[[fresh.steps]]` entry with `script = "scripts/weather.py"`. It reads `timezone` and `[weather]` from `from_env().config`, stages its rows with `staging.write("open-meteo", "weather", rows, window=(first, last))`, and needs only `urllib.request` and `json` from the standard library (see [AGENTS.md](../../AGENTS.md#writing-a-source-script)).

## Watch out for

- **Daylight saving time.** Open-Meteo resolves the time zone's UTC offset "at request time" and uses it "for ISO 8601 timestamps and daily boundaries throughout the response. Daylight saving time (DST) changes within the requested range are ignored" ([Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)). A request made in winter for summer dates gets days that run from 23:00 to 23:00 local summer time. Open-Meteo says this is by design and won't change, as it would break the API ([issue 1545](https://github.com/open-meteo/open-meteo/issues/1545)). The effect is one hour of a day's temperature and precipitation; daylight is unaffected. Accept it, or for exact local days fetch `hourly` values with `timeformat=unixtime` and total them per local date in the script.
- **Observed versus forecast.** The archive is reanalysis: a model run over past observations, for a grid cell, not a station reading. Its newest days come from ECMWF IFS and ERA5 follows about 5 days later ([Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)), so a recent day's values may change between runs. The Forecast API's `past_days` are forecasts. Neither is a measurement at the person's door.
- **Precipitation can differ from a local gauge.** Showers are local and a grid cell is several kilometres wide.
- **Don't use `timezone=auto`** or the default `GMT`; both can put days on different dates from the rest of dotlife.
- **Rate limits.** A loop that requests one day at a time over years can hit 600 calls a minute ([Terms](https://open-meteo.com/en/terms)). Request the whole range at once.

## Not in the format

- Minimum and maximum temperature (`temperature_2m_min`, `temperature_2m_max`).
- Apparent ("feels like") temperature (`apparent_temperature_mean`).
- Sunshine duration in seconds (`sunshine_duration`), which differs from daylight.
- Rain and snowfall separately (`rain_sum` in mm, `snowfall_sum` in cm) and hours with precipitation (`precipitation_hours`).
- Sunrise and sunset times (`sunrise`, `sunset`).
- Maximum wind speed and gusts (`wind_speed_10m_max`, `wind_gusts_10m_max`).
- Weather code (`weather_code`) and solar radiation sum (`shortwave_radiation_sum`).

## Sources

- [Open-Meteo: Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo: Weather Forecast API](https://open-meteo.com/en/docs)
- [Open-Meteo: Terms & Privacy](https://open-meteo.com/en/terms)
- [Open-Meteo: Licence](https://open-meteo.com/en/licence)
- [open-meteo/open-meteo issue 1545: Time change issue with daily data](https://github.com/open-meteo/open-meteo/issues/1545)
- [Meteostat Developers](https://dev.meteostat.net/)
- [Meteostat: Time series](https://dev.meteostat.net/data/timeseries)
- [Meteostat: Daily data](https://dev.meteostat.net/data/timeseries/daily)
- [Meteostat: JSON API](https://dev.meteostat.net/api)
- [Meteostat: License](https://dev.meteostat.net/license)

Checked 2026-10-29.
