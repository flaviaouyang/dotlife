# Google Calendar

Google Calendar is Google's web and mobile calendar. It can fill `time.csv` (hours per category per day) from timed events and, if the person wants, `events.csv`, `social.csv` and `travel.csv` from calendars or keywords they set aside for that.

## What it fills

| dotlife column | From | Notes |
| --- | --- | --- |
| `time.date` | `start.dateTime` and `end.dateTime`, converted to the `timezone` in `config.toml` | An event crossing local midnight is split, and each part counts toward its own date. |
| `time.category` | The calendar (`summary`), its colour (`backgroundColor`), the event colour (`colorId`) or a keyword in the title | The person's rule, recorded in `sources.md`. The title is read only to match a keyword and is never written. |
| `time.hours` | Duration of timed events | Sum per date and category, counting overlapping time once. Minutes / 60, rounded to 2 decimals. |
| `time.source` | | `google-calendar` |
| `events.date`, `events.label` | All-day events (`start.date`) in a calendar or with a keyword the person names for life events | Optional. Label written by the person or agreed with them; see below. |
| `events.source` | | `google-calendar`, the same value as in `time.csv`. Required. |
| `social.social_h` | Hours of the category the person names as social | Optional and sensitive. Same calculation as `time.hours`. |
| `travel.travel_day`, `travel.country` | All-day events in a calendar or with a keyword the person names for travel | Optional and sensitive. `1` for each date covered. `country` only from an explicit code in their convention. |

## Getting the data out

### Google Calendar API v3 (best for a repeatable script)

- **Setup.** Following Google's Python quickstart: enable the Google Calendar API in a Google Cloud project, configure the OAuth consent screen (Google Auth platform > Branding), create an OAuth client of type Desktop app (Google Auth platform > Clients), and save its JSON as `credentials.json`. The first run opens a browser for consent and saves the tokens to `token.json` ([Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python)). Keep both files outside the repo, or at least out of git.
- **Scope.** `https://www.googleapis.com/auth/calendar.readonly` ("See and download any calendar you can access") covers both the list of calendars and their events ([Choose Google Calendar API scopes](https://developers.google.com/workspace/calendar/api/auth)). `calendar.events.readonly` also works for `events.list` ([Events: list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)), but then calendar names need `calendar.calendarlist.readonly` as well.
- **Testing-mode tokens expire.** An app with external user type and "Testing" publishing status gets a refresh token that expires in 7 days ([Using OAuth 2.0 to access Google APIs](https://developers.google.com/identity/protocols/oauth2)), so a weekly sync would need a new consent each time while the app stays in Testing.
- **Calendars.** `calendarList` gives each calendar's `summary` (title), the person's own `summaryOverride`, `backgroundColor` (hex), `timeZone` and whether it is `primary` ([CalendarList](https://developers.google.com/workspace/calendar/api/v3/reference/calendarList)).
- **Events.** `GET https://www.googleapis.com/calendar/v3/calendars/{calendarId}/events` with ([Events: list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)):
  - `singleEvents=true` to "expand recurring events into instances" (the default is `false`);
  - `timeMin` and `timeMax`, RFC 3339 timestamps with an offset. `timeMin` filters on the event's end and `timeMax` on its start, both exclusive, so events overlapping the window's edges are included and must be clipped;
  - `orderBy=startTime` (only allowed with `singleEvents=true`);
  - `maxResults` up to 2500 (default 250) and `pageToken` to page through;
  - `showDeleted` stays `false` (the default), which leaves out cancelled events;
  - optionally `timeZone` for the response; the default is the calendar's zone.
- **Fields used** ([Events](https://developers.google.com/workspace/calendar/api/v3/reference/events)): `start` and `end` (`dateTime` for timed events, `date` for all-day ones; `end` is exclusive); `status` (`confirmed`, `tentative`, `cancelled`); `attendees[]`, where `self` marks the person's own entry and `responseStatus` is `needsAction`, `declined`, `tentative` or `accepted`; `eventType` (`default`, `focusTime`, `outOfOffice`, `workingLocation`, `birthday`, `fromGmail`); `transparency` (`opaque` is busy, `transparent` is available); `colorId`, a key into the colors endpoint.
- **Quotas.** 10,000 requests per minute per project and 600 per minute per user; going over returns `403 usageLimits` or `429 usageLimits`. Use under 1,000,000 requests a day is not billed, and Google plans to charge for exceeding quota "later in 2026" with at least 90 days' notice ([Manage quotas](https://developers.google.com/workspace/calendar/api/guides/quota)). A personal sync makes a handful of requests.

### Secret address in iCal format (no OAuth)

Each calendar has a private `.ics` feed: Settings > Settings for my calendars > (the calendar) > Integrate calendar > "Secret address in iCal format". Anyone with the address can see the calendar; Reset creates a new one and invalidates the old ([Share your calendar with someone](https://support.google.com/calendar/answer/37648)). For a work or school account, the admin's sharing settings may hide it (same page).

A script can download this feed on every sync without OAuth. Store the address like a password, outside the repo and never in `sources.md`. The feed is iCalendar, so recurring events come as rules and must be expanded (see [Mapping](#mapping-to-the-format)).

### Export from Google Calendar (by hand)

Exporting works only from a computer, not the app ([Export events from your Google Calendar](https://support.google.com/calendar/answer/37111)):

- All calendars: Settings (gear icon) > Settings > Import & export > Export. A `.zip` downloads, containing the `.ics` files.
- One calendar: hover over it under "My calendars", choose More > Settings and sharing, then Export calendar under "Calendar settings". One `.ics` file downloads.
- It needs the "Make changes and manage sharing" permission on the calendar, and an organisation's admin may restrict exporting (same page).

This suits a one-off backfill.

### Google Takeout

Calendar is one of the products Takeout can export ([Download your Google data](https://support.google.com/accounts/answer/3024190)). Google's help page doesn't state the format of the Calendar export; check the archive's own description file before relying on it. The settings export above is simpler.

### Connectors in AI tools

- **Claude's Google Calendar connector** reads calendars on Pro, Max, Team and Enterprise plans; it is read-only and cannot create or change events ([Google Calendar connector](https://claude.com/docs/connectors/google/calendar)).
- **Google's Calendar MCP server** (`https://calendarmcp.googleapis.com/mcp/v1`) is a Google-hosted remote MCP server in Developer Preview. It needs membership of the Google Workspace Developer Preview Program, a Cloud project with the Calendar API and Calendar MCP API enabled, and an OAuth client; it lists Claude.ai and Claude Desktop (via a custom connector) among supported clients ([Configure the Calendar MCP server](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server)). Its tools include `list_calendars` and `list_events` ([Calendar MCP reference](https://developers.google.com/workspace/calendar/api/v3/reference/mcp)); how `list_events` handles recurring events was not documented on the pages checked.

A script against the API is preferred: summing hours by hand from a connector's answers is slow and error-prone, and connectors don't guarantee that every recurring occurrence and declined invitation is visible. If a connector is the only way, transcribe the times exactly.

## Mapping to the format

The rules are the same in the Apple, Google and Outlook guides.

### Categories

- The person chooses one rule and `sources.md` records it: by calendar (calendar "Work" becomes `work`), by colour (the calendar's `backgroundColor`, or an event's own `colorId`), or by a keyword in the title (a title starting `#study` becomes `study`). If both are used, say in `sources.md` which wins.
- Use short lowercase category names, e.g. `work`, `study`, `exercise`, `chores`, `leisure`, `social`, and keep them stable over time.
- An event that matches no rule is skipped, and the sync reports how many hours were skipped. Map unmatched events to `other` only if `sources.md` says so.
- Never write event titles, attendee names, locations or notes to `time.csv`. Only the category leaves the calendar.

### Which events count

- Only timed events (`start.dateTime`) are hours. All-day events (`start.date`) never add hours; they can feed `events.csv` or `travel.csv` instead.
- Expand recurring events into their occurrences, including moved occurrences and without the deleted ones. With the API, `singleEvents=true` does it; with an `.ics` feed or export, expand `RRULE`, `RDATE`, `EXDATE` and `RECURRENCE-ID` with a library such as [recurring-ical-events](https://pypi.org/project/recurring-ical-events/).
- Skip events whose `status` is `cancelled` (`STATUS:CANCELLED` in `.ics`, defined in [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545)) and events the person declined (`responseStatus` of `declined` on the attendee with `self` true; `PARTSTAT=DECLINED` in `.ics`).
- Tentative and unanswered invitations count unless `sources.md` says otherwise. Events marked available (`transparency` of `transparent`) count too, unless `sources.md` says to skip them.
- `workingLocation` events say where the person works, not how long, so skip them. `focusTime` events are ordinary time. `outOfOffice` and `birthday` events are not hours.

### Time zones and dates

- Convert each start and end to the `timezone` in `config.toml`. API times are RFC 3339 with an offset; `.ics` times come with a `TZID`, in UTC (ending in `Z`), or floating (no zone).
- Read a floating time as a local time in the configured zone.
- Split an event at each local midnight; each part counts toward its own date. This differs from workouts, which count toward the start date, because time use is hours spent on each day.
- Work out durations from absolute instants, so an event across a daylight saving change counts the hours that really passed.

### Hours per day

- Follow the overlap rules under [Time use in FORMAT.md](../../FORMAT.md#time-use): merge each category's intervals, then give time that two categories share to the one `sources.md` ranks first. The validator reports a day whose rows add up to more than 24 hours.
- `hours` = minutes / 60, rounded to 2 decimals. Write a row only when a category has time that day; a day with no row has no tracked time, so never write `0`.
- Stop at the current time; don't write hours for events that haven't happened yet.
- `source` is `google-calendar`.

Example rows (made up):

```csv
date,category,source,hours
2026-03-02,work,google-calendar,6.5
2026-03-02,exercise,google-calendar,1
```

### Re-syncing

Calendars are edited after the fact: meetings move, get cancelled or are entered late. On each sync, recompute a recent window (for example the last 30 days) and stage it with `window=(first, last)`, so every staged row for those dates is replaced rather than appended to. A `command` script writes `data/sources/<source>/time.csv` itself and does the same.

### Optional: life events, social time and travel

Social and travel are sensitive categories. Ask before switching either on in `config.toml`.

- **`events.csv`.** Only all-day events from a calendar or keyword the person names for life events. Titles often contain names, so write a short label the person agrees to, not the raw title. Write `google-calendar` in `source`.
- **`travel.csv`.** All-day events from a travel calendar or keyword: `travel_day` is `1` for each date the event covers. `end.date` is exclusive ([Events](https://developers.google.com/workspace/calendar/api/v3/reference/events)), so a 3 to 5 March trip has an end date of 6 March. Fill `country` only from an explicit code in the convention (e.g. `#travel:JP`), never from a location field.
- **`social.csv`.** `social_h` is the hours of the category the person names as social, worked out as above, written only on days that have some.

## Watch out for

- **`singleEvents` left off.** Without it, a weekly meeting appears once, at its first date, and the hours are badly undercounted.
- **Edges of the window.** `timeMin` and `timeMax` match on overlap, so clip events that start before or end after the window.
- **7-day tokens.** A testing-mode OAuth app's refresh token stops working after a week.
- **Shared and subscribed calendars.** `calendarList` returns every calendar the person is subscribed to, not only their own. Read only the calendars `sources.md` names.
- **Duplicated calendars.** The same Google calendar can also appear in Apple Calendar or Outlook. Count each calendar from one source only, as ranked in `sources.md`.
- **Plans, not records.** A calendar shows what was planned. Past events that didn't happen stay unless the person deletes them.
- **Raw exports hold names.** `.ics` files contain titles, attendees and notes. Don't commit them; delete them once imported.

## Not in the format

- Number of meetings or events per day.
- Hours with other attendees versus alone.
- Focus time booked (`focusTime`) as its own measure.
- Out-of-office days (`outOfOffice`).
- Working location (home or office) per day.
- Event start times (e.g. first meeting of the day).

## Sources

- [Export events from your Google Calendar](https://support.google.com/calendar/answer/37111)
- [Share your calendar with someone (secret address)](https://support.google.com/calendar/answer/37648)
- [Download your Google data (Takeout)](https://support.google.com/accounts/answer/3024190)
- [Events: list (Calendar API v3)](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)
- [Events resource (Calendar API v3)](https://developers.google.com/workspace/calendar/api/v3/reference/events)
- [CalendarList resource (Calendar API v3)](https://developers.google.com/workspace/calendar/api/v3/reference/calendarList)
- [Choose Google Calendar API scopes](https://developers.google.com/workspace/calendar/api/auth)
- [Manage quotas (Calendar API)](https://developers.google.com/workspace/calendar/api/guides/quota)
- [Python quickstart (Calendar API)](https://developers.google.com/workspace/calendar/api/quickstart/python)
- [Using OAuth 2.0 to access Google APIs](https://developers.google.com/identity/protocols/oauth2)
- [Configure the Calendar MCP server](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server)
- [Calendar MCP server reference](https://developers.google.com/workspace/calendar/api/v3/reference/mcp)
- [Google Calendar connector (Claude docs)](https://claude.com/docs/connectors/google/calendar)
- [RFC 5545: iCalendar](https://www.rfc-editor.org/rfc/rfc5545)
- [recurring-ical-events (PyPI)](https://pypi.org/project/recurring-ical-events/)

Checked 2026-10-29.
