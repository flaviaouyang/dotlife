# Apple Calendar

Calendar is Apple's calendar app on macOS and iOS. It can fill `time.csv` (hours per category per day) from timed events and, if the person wants, `events.csv`, `social.csv` and `travel.csv` from calendars or keywords they set aside for that.

## What it fills

| dotlife column | From | Notes |
| --- | --- | --- |
| `time.date` | Event start and end, converted to the `timezone` in `config.toml` | An event crossing local midnight is split, and each part counts toward its own date. |
| `time.category` | The calendar, the calendar's colour, or a keyword in the title | The person's rule, recorded in `sources.md`. The title is read only to match a keyword and is never written. |
| `time.hours` | Duration of timed events | Sum per date and category, counting overlapping time once. Minutes / 60, rounded to 2 decimals. |
| `time.source` | | `apple-calendar` |
| `events.date`, `events.label` | All-day events in a calendar or with a keyword the person names for life events | Optional. Label written by the person or agreed with them; see below. |
| `events.source` | | `apple-calendar`, the same value as in `time.csv`. Required. |
| `social.social_h` | Hours of the category the person names as social | Optional and sensitive. Same calculation as `time.hours`. |
| `travel.travel_day`, `travel.country` | All-day events in a calendar or with a keyword the person names for travel | Optional and sensitive. `1` for each date covered. `country` only from an explicit code in their convention. |

## Getting the data out

### A Swift script with EventKit (best for a repeatable script)

EventKit is Apple's framework for reading calendar data on the device. A short Swift script run on the Mac reads every calendar shown in Calendar without any export step.

- **Access.** Apps "can't request read-only access"; to read events an app "needs full access" ([Accessing the event store](https://developer.apple.com/documentation/eventkit/accessing-the-event-store)). Request it with `requestFullAccessToEvents`, available from macOS 14 and iOS 17 ([requestFullAccessToEvents(completion:)](https://developer.apple.com/documentation/eventkit/ekeventstore/requestfullaccesstoevents(completion:))). Write-only access is not enough: with it, a request for calendars returns "a single virtual calendar" and requests for events "return no results" ([Accessing the event store](https://developer.apple.com/documentation/eventkit/accessing-the-event-store)).
- **The permission prompt.** The system asks "only the first time" an app requests full access; later runs reuse the answer ([requestFullAccessToEvents(completion:)](https://developer.apple.com/documentation/eventkit/ekeventstore/requestfullaccesstoevents(completion:))). If the script fetched events before access was granted, it must call `reset()` on the event store to see data (same page). The person can review and change the grant in System Settings > Privacy & Security > Calendars, where some apps can be given either full access or only permission to add events ([Allow apps to use your calendar information on Mac](https://support.apple.com/guide/mac-help/allow-apps-to-use-your-calendar-information-mh43609/mac)). It must be full access.
- **Info.plist and command-line tools.** Apps declare why they want access with `NSCalendarsFullAccessUsageDescription` in their `Info.plist` ([NSCalendarsFullAccessUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nscalendarsfullaccessusagedescription); [Accessing the event store](https://developer.apple.com/documentation/eventkit/accessing-the-event-store)). Apple's documentation does not describe how a plain Swift script or command-line tool, which has no `Info.plist` of its own, is attributed. Unverified, from a community project: macOS attributes the permission to the app that launched the tool (e.g. Terminal), and a grant made from one terminal does not cover another host app such as a desktop AI client ([mcp-server-apple-events](https://github.com/FradSer/mcp-server-apple-events)). So run the script from the same app each time, and if no prompt appears, look for that app in the Calendars list in Privacy & Security.
- **Fetching.** Build a predicate with `predicateForEvents(withStart:end:calendars:)` and pass it to `events(matching:)`. The predicate covers at most four years; a longer range "is shortened to the first four years" ([predicateForEvents](https://developer.apple.com/documentation/eventkit/ekeventstore/predicateforevents(withstart:end:calendars:))), so fetch in chunks of a year or less. `events(matching:)` is synchronous and returns only committed events ([events(matching:)](https://developer.apple.com/documentation/eventkit/ekeventstore/events(matching:))).
- **Fields used.** `calendar.title` and `calendar.cgColor` for the category ([title](https://developer.apple.com/documentation/eventkit/ekcalendar/title), [cgColor](https://developer.apple.com/documentation/eventkit/ekcalendar/cgcolor)); `isAllDay` ([isAllDay](https://developer.apple.com/documentation/eventkit/ekevent/isallday)); `startDate` and `endDate`; `status`, where only `canceled` should change what you do ([status](https://developer.apple.com/documentation/eventkit/ekevent/status)); `attendees`, where the participant with `isCurrentUser` is the person and `participantStatus` holds their answer ([isCurrentUser](https://developer.apple.com/documentation/eventkit/ekparticipant/iscurrentuser), [participantStatus](https://developer.apple.com/documentation/eventkit/ekparticipant/participantstatus)); `timeZone`, which is nil for a floating event ([timeZone](https://developer.apple.com/documentation/eventkit/ekcalendaritem/timezone)).
- **Recurring events.** The predicate matches "events that occur within a given date range", and each recurring instance carries an `occurrenceDate` ([predicateForEvents](https://developer.apple.com/documentation/eventkit/ekeventstore/predicateforevents(withstart:end:calendars:)), [occurrenceDate](https://developer.apple.com/documentation/eventkit/ekevent/occurrencedate)). Apple's pages don't spell out that every occurrence is returned as its own event; check it once against a known weekly event before trusting the totals.

The script can be run with `swift` or compiled once with `swiftc`. It needs no account, developer membership or network access.

### Export from Calendar on Mac (by hand)

- One calendar as `.ics`: click the calendar's name in the calendar list (View > Show Calendar List if hidden), then choose File > Export > Export, and save ([Import or export calendars on Mac](https://support.apple.com/guide/calendar/import-or-export-calendars-icl1023/mac)).
- All calendars: File > Export > Calendar Archive saves one archive of every calendar (same page). The archive is meant for restoring into Calendar, not for reading; export the calendars you need as `.ics` instead.

An `.ics` export is a snapshot. Recurring events are stored once with their rules, so a script must expand them itself (see [Mapping](#mapping-to-the-format)). This suits a one-off backfill; the EventKit script suits regular syncs.

### iCloud calendars over CalDAV

iCloud calendars can be read from any machine over CalDAV, which suits a script running outside a Mac.

- Third-party apps sign in with an app-specific password, not the Apple Account password. Generating one needs two-factor authentication; create it at account.apple.com under Sign-In and Security > App-Specific Passwords. An account can have 25 active, and changing the main password revokes all of them ([Sign in to apps with your Apple Account using app-specific passwords](https://support.apple.com/en-us/102654)).
- The server is `caldav.icloud.com` and the username is the Apple Account email. Apple's support pages don't state these; they come from a third-party guide ([iCloud CalDAV settings](https://cli.nylas.com/guides/icloud-caldav-settings)).
- Since October 2025 Apple also lets "supported third-party apps" reach iCloud Calendar through Apple Account authorisation instead of an app-specific password ([Apple Support 121539](https://support.apple.com/en-us/121539)). For developers this is still a pilot with no published technical documentation ([Apple Developer Forums](https://developer.apple.com/forums/thread/850313)), so a personal script should use an app-specific password.
- CalDAV defines a `CALDAV:expand` request that makes the server return each recurrence instance separately ([RFC 4791, 9.6.5](https://www.rfc-editor.org/rfc/rfc4791#section-9.6.5)). Whether iCloud honours it was not verified; expanding locally is safe either way.
- Store the password outside the repo (e.g. in the macOS Keychain or an environment variable), never in `sources.md` or a script.

### AppleScript or JXA (not recommended)

Calendar can be scripted with AppleScript or JavaScript for Automation, but it is slow: one user's query over Calendar events took 61 to 112 seconds, against an instant Python alternative ([All this: Applesloth](https://leancrew.com/all-this/2020/03/applesloth/)). Community reports also describe date-range queries that miss recurring events, because a series' start date is its first occurrence ([MacScripter](https://www.macscripter.net/t/find-recurring-event-that-has-an-item-within-date-range/76198)). Both are community sources. Use EventKit instead.

### Connectors in AI tools

No Apple-made connector for AI tools was found. Community MCP servers for Apple Calendar exist; they use EventKit and need the same full-access grant ([mcp-server-apple-events](https://github.com/FradSer/mcp-server-apple-events)). A script is preferred over a connector here, because the script can read every event directly.

## Mapping to the format

The rules are the same in the Apple, Google and Outlook guides.

### Categories

- The person chooses one rule and `sources.md` records it: by calendar (calendar "Work" becomes `work`), by calendar colour, or by a keyword in the title (a title starting `#study` becomes `study`). In Apple Calendar colour belongs to the calendar, so colour and calendar give the same result.
- Use short lowercase category names, e.g. `work`, `study`, `exercise`, `chores`, `leisure`, `social`, and keep them stable over time.
- An event that matches no rule is skipped, and the sync reports how many hours were skipped. Map unmatched events to `other` only if `sources.md` says so.
- Never write event titles, attendee names, locations or notes to `time.csv`. Only the category leaves the calendar.

### Which events count

- Only timed events are hours. All-day events (`isAllDay`) never add hours; they can feed `events.csv` or `travel.csv` instead.
- Expand recurring events into their occurrences, including moved occurrences and without the deleted ones. In an `.ics` file these are `RRULE`, `RDATE`, `EXDATE` and `RECURRENCE-ID`; a library such as [recurring-ical-events](https://pypi.org/project/recurring-ical-events/) does this.
- Skip events whose status is cancelled (`canceled` in EventKit, `STATUS:CANCELLED` in `.ics`, defined in [RFC 5545](https://www.rfc-editor.org/rfc/rfc5545)) and events the person declined (`participantStatus` of `declined` for the current user; `PARTSTAT=DECLINED` in `.ics`).
- Tentative and unanswered invitations count unless `sources.md` says otherwise. Events marked free (availability) count too, unless `sources.md` says to skip them.

### Time zones and dates

- Convert each start and end to the `timezone` in `config.toml`. EventKit returns events "in the default time zone" ([predicateForEvents](https://developer.apple.com/documentation/eventkit/ekeventstore/predicateforevents(withstart:end:calendars:))), i.e. the Mac's, so convert explicitly rather than relying on the system setting. `.ics` times come with a `TZID`, in UTC (ending in `Z`), or floating.
- A floating event has no zone and "occurs at a given time regardless of the time zone" ([timeZone](https://developer.apple.com/documentation/eventkit/ekcalendaritem/timezone)). Read its clock times as local times in the configured zone.
- Split an event at each local midnight; each part counts toward its own date. This differs from workouts, which count toward the start date, because time use is hours spent on each day.
- Work out durations from absolute instants, so an event across a daylight saving change counts the hours that really passed.

### Hours per day

- Follow the overlap rules under [Time use in FORMAT.md](../../FORMAT.md#time-use): merge each category's intervals, then give time that two categories share to the one `sources.md` ranks first. The validator reports a day whose rows add up to more than 24 hours.
- `hours` = minutes / 60, rounded to 2 decimals. Write a row only when a category has time that day; a day with no row has no tracked time, so never write `0`.
- Stop at the current time; don't write hours for events that haven't happened yet.
- `source` is `apple-calendar`.

Example rows (made up):

```csv
date,category,source,hours
2026-03-02,work,apple-calendar,6.5
2026-03-02,exercise,apple-calendar,1
```

### Re-syncing

Calendars are edited after the fact: meetings move, get cancelled or are entered late. On each sync, recompute a recent window (for example the last 30 days) and replace every `time.csv` row from this source for the dates in that window, instead of appending.

### Optional: life events, social time and travel

Social and travel are sensitive categories. Ask before switching either on in `config.toml`.

- **`events.csv`.** Only all-day events from a calendar or keyword the person names for life events. Titles often contain names, so write a short label the person agrees to, not the raw title. Write `apple-calendar` in `source`.
- **`travel.csv`.** All-day events from a travel calendar or keyword: `travel_day` is `1` for each date the event covers. In `.ics`, the end date of an all-day event is not inclusive ([RFC 5545, 3.6.1](https://www.rfc-editor.org/rfc/rfc5545#section-3.6.1)), so a 3 to 5 March trip ends on 6 March. Fill `country` only from an explicit code in the convention (e.g. `#travel:JP`), never from a location field.
- **`social.csv`.** `social_h` is the hours of the category the person names as social, worked out as above, written only on days that have some.

## Watch out for

- **Write-only access returns nothing.** A script granted only "add events" sees one virtual calendar and no events. Switch it to full access in Privacy & Security.
- **Different launcher, different grant.** Running the same script from another terminal or an AI desktop app may prompt again or fail (community report above).
- **Four-year cap.** A single EventKit query longer than four years is silently cut short.
- **Duplicated calendars.** The same calendar can appear twice, e.g. a Google account added to Calendar and also synced by the Google guide. Count each calendar from one source only, as ranked in `sources.md`.
- **Plans, not records.** A calendar shows what was planned. Past events that didn't happen stay unless the person deletes them.
- **Raw exports hold names.** `.ics` files contain titles, attendees and notes. Don't commit them; delete them once imported.

## Not in the format

- Number of meetings or events per day.
- Hours with other attendees versus alone.
- Event start times (e.g. first meeting of the day).
- Locations of events.
- Hours marked free versus busy.

## Sources

- [Import or export calendars in Calendar on Mac](https://support.apple.com/guide/calendar/import-or-export-calendars-icl1023/mac)
- [Allow apps to use your calendar information on Mac](https://support.apple.com/guide/mac-help/allow-apps-to-use-your-calendar-information-mh43609/mac)
- [Accessing the event store (EventKit)](https://developer.apple.com/documentation/eventkit/accessing-the-event-store)
- [requestFullAccessToEvents(completion:)](https://developer.apple.com/documentation/eventkit/ekeventstore/requestfullaccesstoevents(completion:))
- [NSCalendarsFullAccessUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nscalendarsfullaccessusagedescription)
- [predicateForEvents(withStart:end:calendars:)](https://developer.apple.com/documentation/eventkit/ekeventstore/predicateforevents(withstart:end:calendars:))
- [events(matching:)](https://developer.apple.com/documentation/eventkit/ekeventstore/events(matching:))
- [EKEvent isAllDay](https://developer.apple.com/documentation/eventkit/ekevent/isallday)
- [EKEvent status](https://developer.apple.com/documentation/eventkit/ekevent/status)
- [EKEvent occurrenceDate](https://developer.apple.com/documentation/eventkit/ekevent/occurrencedate)
- [EKCalendarItem timeZone](https://developer.apple.com/documentation/eventkit/ekcalendaritem/timezone)
- [EKCalendar title](https://developer.apple.com/documentation/eventkit/ekcalendar/title)
- [EKCalendar cgColor](https://developer.apple.com/documentation/eventkit/ekcalendar/cgcolor)
- [EKParticipant isCurrentUser](https://developer.apple.com/documentation/eventkit/ekparticipant/iscurrentuser)
- [EKParticipant participantStatus](https://developer.apple.com/documentation/eventkit/ekparticipant/participantstatus)
- [Sign in to apps with your Apple Account using app-specific passwords (Apple Support 102654)](https://support.apple.com/en-us/102654)
- [Access iCloud Mail, Calendar and Contacts in supported third-party apps (Apple Support 121539)](https://support.apple.com/en-us/121539)
- [How can a Windows CalDAV app use Apple Account authorization for iCloud Calendar? (Apple Developer Forums)](https://developer.apple.com/forums/thread/850313)
- [iCloud CalDAV settings (Nylas, third party)](https://cli.nylas.com/guides/icloud-caldav-settings)
- [RFC 4791: CalDAV](https://www.rfc-editor.org/rfc/rfc4791)
- [RFC 5545: iCalendar](https://www.rfc-editor.org/rfc/rfc5545)
- [recurring-ical-events (PyPI)](https://pypi.org/project/recurring-ical-events/)
- [Applesloth (All this, community)](https://leancrew.com/all-this/2020/03/applesloth/)
- [Find recurring event that has an item within date range (MacScripter, community)](https://www.macscripter.net/t/find-recurring-event-that-has-an-item-within-date-range/76198)
- [mcp-server-apple-events (GitHub, community)](https://github.com/FradSer/mcp-server-apple-events)

Checked 2026-10-29.
