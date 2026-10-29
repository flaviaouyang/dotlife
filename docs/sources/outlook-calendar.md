# Outlook calendar

The Outlook calendar is Microsoft's calendar in Outlook and Microsoft 365, for both work or school accounts and personal Microsoft accounts (outlook.com). It can fill `time.csv` (hours per category per day) from timed events and, if the person wants, `events.csv`, `social.csv` and `travel.csv` from calendars or Outlook categories they set aside for that.

## What it fills

| dotlife column | From | Notes |
| --- | --- | --- |
| `time.date` | `start` and `end`, converted to the `timezone` in `config.toml` | An event crossing local midnight is split, and each part counts toward its own date. |
| `time.category` | The calendar, the event's Outlook `categories`, or a keyword in the `subject` | The person's rule, recorded in `sources.md`. The subject is read only to match a keyword and is never written. |
| `time.hours` | Duration of timed events | Sum per date and category, counting overlapping time once. Minutes / 60, rounded to 2 decimals. |
| `time.source` | | `outlook` |
| `events.date`, `events.label` | All-day events (`isAllDay`) in a calendar or category the person names for life events | Optional. Label written by the person or agreed with them; see below. |
| `events.source` | | `outlook`, the same value as in `time.csv`. Required. |
| `social.social_h` | Hours of the category the person names as social | Optional and sensitive. Same calculation as `time.hours`. |
| `travel.travel_day`, `travel.country` | All-day events in a calendar or category the person names for travel | Optional and sensitive. `1` for each date covered. `country` only from an explicit code in their convention. |

## Getting the data out

### Microsoft Graph calendarView (best for a repeatable script)

- **Endpoint.** `GET https://graph.microsoft.com/v1.0/me/calendarView?startDateTime=...&endDateTime=...` for the default calendar, or `/me/calendars/{id}/calendarView` for another one. It returns "the occurrences, exceptions, and single instances of events" in the range, so recurring events arrive already expanded. Both parameters are required ISO 8601 values; without an offset they are read as UTC ([List calendarView](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0)).
- **Time zone of the response.** Start and end come back in UTC unless the request sends a `Prefer: outlook.timezone` header (same page). Taking UTC and converting in the script is simplest.
- **Permissions.** The least privileged permission is `Calendars.ReadBasic`, for work or school accounts and personal Microsoft accounts alike; `Calendars.Read` is the next step up ([List calendarView](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0)). `Calendars.ReadBasic` reads events "except for properties such as body, attachments, and extensions", and neither delegated permission needs admin consent ([Permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference)). If `categories` come back empty under `Calendars.ReadBasic`, try `Calendars.Read`; this was not verified.
- **Sign-in.** Register an app in the Microsoft Entra admin center (App registrations) and use delegated sign-in as the person. For a script, the device code flow suits: the script shows a code, the person signs in on a web page, and the script receives access and refresh tokens (refresh tokens need the `offline_access` scope). The tenant can be `common`, `consumers` (personal accounts) or `organizations`, and Microsoft recommends using MSAL rather than the raw protocol ([OAuth 2.0 device authorization grant](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code)). Keep tokens outside the repo.
- **Paging.** Follow `@odata.nextLink` until it is no longer returned; page sizes differ between APIs ([Paging Microsoft Graph data](https://learn.microsoft.com/en-us/graph/paging)).
- **Limits.** Per app and mailbox: 10,000 requests in 10 minutes and four concurrent requests ([Throttling limits](https://learn.microsoft.com/en-us/graph/throttling-limits)). A personal sync makes a handful.
- **Fields used** ([event resource type](https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0)): `start` and `end` (UTC by default); `isAllDay`; `isCancelled`; `responseStatus` (the person's own response); `showAs` (`free`, `tentative`, `busy`, `oof`, `workingElsewhere`, `unknown`); `type` (`singleInstance`, `occurrence`, `exception`, `seriesMaster`); `categories`, each the `displayName` of one of the person's Outlook categories; `subject`, read only for keyword rules.

### Publish an ICS link from Outlook on the web (no app registration)

In Outlook on the web: Calendar > Settings > Shared calendars > Publish a calendar, choose the calendar and how much detail to show, then Publish. The classic Outlook on the web uses Settings > Calendar > Shared calendars > Calendar publishing. This gives an HTML link and an ICS link; the ICS link can be subscribed to and stays up to date. Unpublish removes it ([Publish your calendar in Outlook on the web](https://support.microsoft.com/office/7ecef8ae-139c-40d9-bae2-a23977ee58d5)). "Published calendars are viewable by anyone with the link" ([Introduction to publishing Internet calendars](https://support.microsoft.com/en-us/office/introduction-to-publishing-internet-calendars-a25e68d6-695a-41c6-a701-103d44ba151d)).

A script can download the ICS link on every sync. Choose a detail level that includes what the category rule needs (titles for a keyword rule). Store the link like a password, outside the repo and never in `sources.md`. Recurring events come as rules and must be expanded (see [Mapping](#mapping-to-the-format)). An organisation may turn publishing off; this was not verified.

### Export from the desktop app (by hand)

- **Classic Outlook for Windows** (Outlook for Microsoft 365, 2024, 2021): select the calendar, File > Save Calendar, then More Options to set the Date Range (or Specify dates) and the Detail, and Save. It writes one `.ics` file; a whole calendar can take a while ([Export an Outlook calendar to Google Calendar](https://support.microsoft.com/en-us/outlook/export-an-outlook-calendar-to-google-calendar)).
- **Classic Outlook, with categories.** A Microsoft community moderator describes exporting the calendar to CSV with File > Open & Export > Import/Export > Export to a file > Comma Separated Values, choosing the Calendar folder and using Map Custom Fields to include Categories ([Microsoft Q&A, June 2026](https://learn.microsoft.com/en-us/answers/questions/5918841/export-calendar-with-categories)). This is a community answer, not documentation.
- **New Outlook for Windows.** The same moderator says new Outlook has no built-in way to export calendar data with categories (same page). A Microsoft 365 roadmap item, "Save calendar events as .ics" in new Outlook for Windows, was listed as in development with general availability targeted for May 2026, according to a third-party mirror of the roadmap ([RM560533](https://mc.merill.net/message/RM560533)); it is about events, not whole calendars. Use publishing or Graph instead.
- **Outlook for Mac.** No Microsoft documentation for exporting a calendar to `.ics` was found. In a 2024 to 2025 community thread, one user says the built-in export produces only an `.olm` archive, and the workarounds offered go through other apps ([Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/4637862/i-want-to-export-my-outlook-calendar-on-a-mac)). Use publishing or Graph.

A file export is a snapshot and suits a one-off backfill.

### Connectors in AI tools

Claude's Microsoft 365 connector reads Outlook, including calendar events, on every Claude plan. It needs a work or school account on a Microsoft Entra tenant, and a Global Administrator must grant tenant consent; personal accounts (outlook.com, hotmail.com, live.com) are not supported ([Microsoft 365 connector](https://claude.com/docs/connectors/microsoft/365)). Write actions, including creating and deleting events, work only if administrators turn them on (same page); syncing needs only reading.

A script against Graph is preferred: summing hours by hand from a connector's answers is slow and error-prone. If a connector is the only way, transcribe the times exactly.

## Mapping to the format

The rules are the same in the Apple, Google and Outlook guides.

### Categories

- The person chooses one rule and `sources.md` records it: by calendar (calendar "Work" becomes `work`), by Outlook category (Outlook's colour categories, so this is the colour rule here), or by a keyword in the subject (a subject starting `#study` becomes `study`). An event can carry several Outlook categories; `sources.md` says which wins.
- Use short lowercase category names, e.g. `work`, `study`, `exercise`, `chores`, `leisure`, `social`, and keep them stable over time.
- An event that matches no rule is skipped, and the sync reports how many hours were skipped. Map unmatched events to `other` only if `sources.md` says so.
- Never write subjects, attendee names, locations or bodies to `time.csv`. Only the category leaves the calendar.

### Which events count

- Only timed events are hours. All-day events (`isAllDay`) never add hours; they can feed `events.csv` or `travel.csv` instead.
- Expand recurring events into their occurrences, including moved occurrences and without the deleted ones. `calendarView` does it; skip any `seriesMaster` that appears. With an `.ics` link or export, expand `RRULE`, `RDATE`, `EXDATE` and `RECURRENCE-ID` with a library such as [recurring-ical-events](https://pypi.org/project/recurring-ical-events/).
- Skip events with `isCancelled` true (`STATUS:CANCELLED` in `.ics`, defined in [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545)) and events the person declined (`responseStatus.response` of `declined`; `PARTSTAT=DECLINED` in `.ics`).
- Tentative and unanswered invitations count unless `sources.md` says otherwise. Events shown as `free` count too, unless `sources.md` says to skip them. `oof` (out of office) events are not hours.

### Time zones and dates

- Convert each start and end to the `timezone` in `config.toml`. Graph returns UTC by default; `.ics` times come with a `TZID`, in UTC (ending in `Z`), or floating (no zone). Graph's `originalStartTimeZone` can be a Windows name such as "Pacific Standard Time" ([List calendarView](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0)); if a `TZID` in an `.ics` file is such a name, map it to an IANA name before converting (whether Outlook's `.ics` files do this was not verified).
- Read a floating time as a local time in the configured zone.
- Split an event at each local midnight; each part counts toward its own date. This differs from workouts, which count toward the start date, because time use is hours spent on each day.
- Work out durations from absolute instants, so an event across a daylight saving change counts the hours that really passed.

### Hours per day

- Follow the overlap rules under [Time use in FORMAT.md](../../FORMAT.md#time-use): merge each category's intervals, then give time that two categories share to the one `sources.md` ranks first. The validator reports a day whose rows add up to more than 24 hours.
- `hours` = minutes / 60, rounded to 2 decimals. Write a row only when a category has time that day; a day with no row has no tracked time, so never write `0`.
- Stop at the current time; don't write hours for events that haven't happened yet.
- `source` is `outlook`.

Example rows (made up):

```csv
date,category,source,hours
2026-03-02,work,outlook,6.5
2026-03-02,exercise,outlook,1
```

### Re-syncing

Calendars are edited after the fact: meetings move, get cancelled or are entered late. On each sync, recompute a recent window (for example the last 30 days) and replace every `time.csv` row from this source for the dates in that window, instead of appending.

### Optional: life events, social time and travel

Social and travel are sensitive categories. Ask before switching either on in `config.toml`.

- **`events.csv`.** Only all-day events from a calendar or Outlook category the person names for life events. Subjects often contain names, so write a short label the person agrees to, not the raw subject. Write `outlook` in `source`.
- **`travel.csv`.** All-day events from a travel calendar or category: `travel_day` is `1` for each date the event covers. An all-day event's start and end are set to midnight ([event resource type](https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0)), and in `.ics` the end date is not inclusive ([RFC 5545, 3.6.1](https://www.rfc-editor.org/rfc/rfc5545#section-3.6.1)), so a 3 to 5 March trip ends at midnight starting 6 March. Fill `country` only from an explicit code in the convention (e.g. `#travel:JP`), never from a location field.
- **`social.csv`.** `social_h` is the hours of the category the person names as social, worked out as above, written only on days that have some.

## Watch out for

- **UTC by default.** Graph times without `Prefer: outlook.timezone` are UTC; forgetting to convert shifts evening events to the wrong date.
- **Work versus personal accounts.** Graph works for both, but the Claude connector only for work or school accounts, and an organisation can limit what apps may do.
- **Publishing detail level.** A link published with busy times only has no titles, so a keyword rule finds nothing.
- **Duplicated calendars.** The same calendar can appear in Outlook, Apple Calendar and Google Calendar through account syncing. Count each calendar from one source only, as ranked in `sources.md`.
- **Plans, not records.** A calendar shows what was planned. Past events that didn't happen stay unless the person deletes them.
- **Raw exports hold names.** `.ics` and CSV exports contain subjects, attendees and notes. Don't commit them; delete them once imported.

## Not in the format

- Number of meetings or events per day.
- Hours with other attendees versus alone.
- Online meeting hours (`isOnlineMeeting`).
- Out-of-office days (`showAs` of `oof`).
- Hours shown as working elsewhere (`workingElsewhere`).
- Event start times (e.g. first meeting of the day).

## Sources

- [List calendarView (Microsoft Graph v1.0)](https://learn.microsoft.com/en-us/graph/api/user-list-calendarview?view=graph-rest-1.0)
- [event resource type (Microsoft Graph v1.0)](https://learn.microsoft.com/en-us/graph/api/resources/event?view=graph-rest-1.0)
- [Microsoft Graph permissions reference](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Microsoft Graph service-specific throttling limits](https://learn.microsoft.com/en-us/graph/throttling-limits)
- [Paging Microsoft Graph data in your app](https://learn.microsoft.com/en-us/graph/paging)
- [OAuth 2.0 device authorization grant (Microsoft identity platform)](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code)
- [Publish your calendar in Outlook on the web](https://support.microsoft.com/office/7ecef8ae-139c-40d9-bae2-a23977ee58d5)
- [Introduction to publishing Internet calendars](https://support.microsoft.com/en-us/office/introduction-to-publishing-internet-calendars-a25e68d6-695a-41c6-a701-103d44ba151d)
- [Export an Outlook calendar to Google Calendar](https://support.microsoft.com/en-us/outlook/export-an-outlook-calendar-to-google-calendar)
- [Export calendar with categories (Microsoft Q&A, community)](https://learn.microsoft.com/en-us/answers/questions/5918841/export-calendar-with-categories)
- [I want to export my Outlook calendar on a Mac? (Microsoft Q&A, community)](https://learn.microsoft.com/en-us/answers/questions/4637862/i-want-to-export-my-outlook-calendar-on-a-mac)
- [RM560533: Outlook: Save calendar events as .ics (Microsoft 365 roadmap mirror, third party)](https://mc.merill.net/message/RM560533)
- [Microsoft 365 connector (Claude docs)](https://claude.com/docs/connectors/microsoft/365)
- [RFC 5545: iCalendar](https://www.rfc-editor.org/rfc/rfc5545)
- [recurring-ical-events (PyPI)](https://pypi.org/project/recurring-ical-events/)

Checked 2026-10-29.
