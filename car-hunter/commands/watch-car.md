---
description: Add, list, remove, or sync cars on your watchlist
argument-hint: "add <id> [note] | remove <id> | list | sync <json>"
allowed-tools: Read, Write, Bash, Glob
---

Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Manage the watchlist for a tracked car. The watchlist lives at `{profile_name}-searches/{profile_name}-watchlist.json` in the user's current workspace. Entries are keyed on the stable `listing_id` captured by `/search-cars` and are used by `/build-dashboard` to render the star column and the "Watched only" filter.

Usage (parse from `$ARGUMENTS`):

- `/watch-car add <listing_id> [note]` - add a listing with an optional free-text note
- `/watch-car list` - print the current watchlist
- `/watch-car remove <listing_id>` - remove an entry
- `/watch-car sync <json>` - replace the whole watchlist with the JSON pasted from the dashboard's "Sync watchlist" button

Follow these steps:

1. Resolve the profile: the active profile above, or the single existing profile in `${CLAUDE_PLUGIN_DATA}/profiles/`, or ask.
2. Watchlist path: `{profile_name}-searches/{profile_name}-watchlist.json` in the current workspace. Create the folder if needed.
3. Read the existing watchlist JSON, or start from `{"listings": {}}`.
4. Apply the subcommand:
    - **add**: require a listing id. Set `listings[<id>] = {"note": "<note or empty>", "added": "<today>"}`.
    - **remove**: require a listing id. Delete `listings[<id>]` if present; otherwise say it was not on the watchlist.
    - **list**: no mutation.
    - **sync**: parse the JSON argument; it must be an object with a `listings` object. Validate that every key is a non-empty listing id, then write it as the complete new watchlist (this is how stars clicked in the dashboard get persisted). Report how many entries were added or removed relative to the previous file.
5. Write the file back with a full overwrite via `Write`.
6. Print the resulting watchlist as one line per entry: `- <listing_id>: <note> (added <date>)`.
7. Remind the user to rerun `/build-dashboard` so the stars update in the rendered HTML.

Notes:
- Listing ids are the stable identifiers from the CSV `listing_id` column: the 15-digit AutoTrader id, or `{source}:{hash}` for other sites. Do not accept composite keys like `42500_Testville`.
- Never write the watchlist under `${CLAUDE_PLUGIN_DATA}` - it is a per-project artefact and belongs next to the dated CSV archive.
- Fail loudly with a short message if `add`/`remove` is missing an id or `sync` JSON is malformed.
