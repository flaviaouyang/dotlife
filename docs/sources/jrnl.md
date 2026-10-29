# jrnl

[jrnl](https://jrnl.sh) is a command-line journal that keeps entries in a plain-text file. dotlife's reflections format is jrnl's plain-text format, so a jrnl journal fills `reflections/` with little or no conversion. It fills nothing else.

Reflections are a sensitive category. Switch it on in `config.toml` only after the person agrees, keep the files in their repo, and quote entries only when they ask.

## What it fills

| dotlife column | From | Notes |
| --- | --- | --- |
| `reflections.time` | The bracketed timestamp that starts each entry | Written with jrnl's `timeformat`; set dotlife's `[reflections] time_format` to the same layout. |
| `reflections.text` | The entry's title line and body | Copied as is. Tags stay in the text; dotlife reads the star and drops it. |

## Getting the data out

### The journal file itself (best for a script)

A single-file jrnl journal is already a plain-text file in the right layout. jrnl writes each entry as `[<time>] <title>`, then the body on the following lines, and adds a space and `*` to the title of a starred entry ([`Entry.py`](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/journals/Entry.py)). A copy of the file needs only to be split by year (see below).

Where the file is:

- On first run, jrnl asks where to create the journal file and whether to encrypt it ([Installation](https://jrnl.sh/en/stable/installation/)), so the location is the person's choice.
- If they accept the default, jrnl puts `journal.txt` in its XDG data directory, `jrnl/` under the user data folder ([`path.py`](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/path.py)). On Linux that folder is `~/.local/share` unless `$XDG_DATA_HOME` says otherwise ([XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/)). The exact folder on macOS and Windows is not stated in jrnl's docs; don't assume it.
- `jrnl --list` prints "the config file location, all configured journals, and their locations" ([Command line reference](https://jrnl.sh/en/stable/reference-command-line/)). Use it rather than guessing.
- The config file is `~/.config/jrnl/jrnl.yaml` by default, or `%USERPROFILE%\.config\jrnl\jrnl.yaml` on Windows ([Configuration file](https://jrnl.sh/en/stable/reference-config-file/)).

### Export with `--format txt`

`jrnl --format txt` (or `--format text`) outputs entries "in the same plain-text format that `jrnl` uses to store your journal on disk", and `--file` writes that output to a file instead of the terminal ([Formats](https://jrnl.sh/en/stable/formats/)). There is no `--export` flag in the current command-line reference; use `--format`. Filters combine with it, so one year at a time is:

```sh
jrnl -year 2025 --format txt --file reflections/2025.txt
```

`-year` shows "entries of a specific year"; `-from` and `-to` are inclusive ("after, or on" and "before, or on") and work too, e.g. `jrnl -from 2025-01-01 -to 2025-12-31 --format txt` ([Command line reference](https://jrnl.sh/en/stable/reference-command-line/)). Don't pass a directory to `--file`: jrnl then writes one file per entry ([Formats](https://jrnl.sh/en/stable/formats/)), which is not what dotlife reads.

This is the way to go for encrypted journals and for folder or Day One journals, because the output is plain text whatever the storage.

### Encrypted journals

dotlife can't read an encrypted journal. Two ways out:

- Export as above. jrnl asks for the password and writes plain text.
- `jrnl --decrypt plain_text_copy.txt` writes a decrypted copy next to the encrypted file and leaves the original untouched. Without a file name, `--decrypt` replaces the encrypted file with plain text ([Encryption](https://jrnl.sh/en/stable/encryption/)).

Either way the plain-text copy is no longer protected by jrnl's encryption. Tell the person, and keep the copy only in their dotlife repo.

### Folder and Day One journals

A folder journal stores entries in `YYYY/MM/DD.txt` files and can't be encrypted; jrnl also reads the Day One Classic format ([Journal types](https://jrnl.sh/en/stable/journal-types/)). For both, use `--format txt` rather than reading the files directly.

### Several journals

The `journals` key in the config names each journal and its path ([Configuration file](https://jrnl.sh/en/stable/reference-config-file/)). Put the journal's name before the filters to pick one, e.g. `jrnl work -n 1` ([Usage](https://jrnl.sh/en/stable/usage/)). dotlife has one reflections folder, so ask which journals to include and record that in `sources.md`. To merge several, export each year from each journal and combine the entries into one `YYYY.txt`, sorted by time.

## Mapping to the format

- **One file a year.** Name each file `reflections/YYYY.txt` (`reflections/2025.txt`). dotlife skips files with other names.
- **Time format.** jrnl's default `timeformat` is `%F %r` ([`config.py`](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/config.py)), which writes times like `2026-08-24 10:40:00 PM`. Python's `strptime`, which dotlife uses, doesn't accept `%F`, so set the spelled-out equivalent:

  ```toml
  [reflections]
  time_format = "%Y-%m-%d %I:%M:%S %p"
  ```

  If the person changed `timeformat` in `jrnl.yaml` (globally or for one journal, since per-journal keys override top-level ones ([Configuration file](https://jrnl.sh/en/stable/reference-config-file/))), copy their value, spelling out any shorthand such as `%F`, `%T` or `%r`. jrnl warns not to change `timeformat` for an existing journal; if old entries use a different layout, export with `--format txt`, which rewrites every entry with the current one. `%p` (AM/PM) depends on the system locale, so check a few lines of the file before setting it.
- **Tags.** jrnl's default `tagsymbols` is `#@` ([`config.py`](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/config.py)), the same as dotlife's default `tag_symbols`. If the person set other symbols in `jrnl.yaml`, copy them to `[reflections] tag_symbols`. Tags then behave the same in both: a tag starts with a tag symbol at the start of a word, can contain letters, digits, `_`, `-`, `+`, `*`, `#` and `/`, and is lowercased, so `@Bob` and `@bob` are one tag ([`Entry.py`](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/journals/Entry.py)).
- **Stars.** jrnl appends a space and `*` to the title line of a starred entry ([`Entry.py`](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/journals/Entry.py)). dotlife reads a star in the same place.
- **Time zone.** jrnl doesn't support `%z` or `%Z` ([Configuration file](https://jrnl.sh/en/stable/reference-config-file/)), so times are local clock times with no offset, as dotlife expects. Entries written while travelling keep the clock time of where they were written.
- **Missing times.** jrnl gives an entry with a date but no time `default_hour` and `default_minute` (09:00 by default) ([Configuration file](https://jrnl.sh/en/stable/reference-config-file/)). Those times are jrnl's, not the person's; copy them as they are and don't adjust them.
- **No `source` column.** Reflections files have none. Record in `sources.md` that `reflections/` comes from jrnl, and which journals.
- **Sync.** Re-export the current year on each sync and replace `reflections/<year>.txt`, rather than appending, so edits and deletions made in jrnl carry over. Only replace a file this way if jrnl is its only source.

A sample entry, made up:

```text
[2026-08-24 10:40:00 PM] Long walk with @bob after work. #health *
Felt clearer afterwards.
```

## Watch out for

- **Markdown.** jrnl entries are free text, and some people write Markdown in them. dotlife shows reflections as plain text, so `**bold**` appears with its asterisks. Leave the text unchanged.
- **Text before the first entry.** Lines above the first `[time]` line belong to no entry; the validator reports them.
- **Encryption.** A plain-text export removes jrnl's protection. Never write one outside the dotlife repo, and never commit it anywhere `sources.md` doesn't name.
- **jrnl version.** The latest release on PyPI is 4.6, from 7 August 2026 ([PyPI](https://pypi.org/project/jrnl/)). jrnl needs Python 3.11 or later and is installed with `pipx install jrnl` ([Installation](https://jrnl.sh/en/stable/installation/)).

## Not in the format

- Entry titles as a separate field: dotlife keeps the title as the first line of the text.
- The JSON export's per-entry fields (use `--format json`): dotlife reads only the plain-text layout.
- Tag counts (`jrnl --tags`): dotlife works these out from the text itself.

## Sources

- [jrnl: Installation](https://jrnl.sh/en/stable/installation/)
- [jrnl: Usage](https://jrnl.sh/en/stable/usage/)
- [jrnl: Configuration file](https://jrnl.sh/en/stable/reference-config-file/)
- [jrnl: Command line reference](https://jrnl.sh/en/stable/reference-command-line/)
- [jrnl: Formats](https://jrnl.sh/en/stable/formats/)
- [jrnl: Journal types](https://jrnl.sh/en/stable/journal-types/)
- [jrnl: Encryption](https://jrnl.sh/en/stable/encryption/)
- [jrnl source: config.py](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/config.py)
- [jrnl source: path.py](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/path.py)
- [jrnl source: journals/Entry.py](https://github.com/jrnl-org/jrnl/blob/develop/jrnl/journals/Entry.py)
- [jrnl on PyPI](https://pypi.org/project/jrnl/)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/)

Checked 2026-10-29.
