---
description: Add, list, or remove cars from your watchlist
allowed-tools: Read, Write, Bash
---

Manage the watchlist for a tracked car. The watchlist lives at `{profile_name}-searches/{profile_name}-watchlist.json` in the user's current workspace. Entries are keyed on the stable `listing_id` captured by `/search-cars` and are used by `/build-dashboard` to render the star column and the "Watched only" filter.

Usage (parse from `$ARGUMENTS`):

- `/watch-car add <listing_id> [note]` - add a listing to the watchlist with an optional free-text note
- `/watch-car list` - print the current watchlist
- `/watch-car remove <listing_id>` - remove an entry

Follow these steps:

1. Resolve the active profile the same way `/search-cars` and `/build-dashboard` do: read `${CLAUDE_PLUGIN_DATA}/profiles/`, ask the user if multiple profiles exist, and select the one whose `profile_name` matches.
2. Determine the watchlist path: `{profile_name}-searches/{profile_name}-watchlist.json` in the user's current workspace. Create the `{profile_name}-searches/` folder if it does not exist.
3. Read the existing watchlist JSON, or start from `{"listings": {}}` if the file does not exist.
4. Parse `$ARGUMENTS`:
    - **add**: require a listing id. Insert or update `listings[<id>] = {"note": "<note or empty>", "added": "<today>"}`.
    - **list**: skip the mutation step.
    - **remove**: require a listing id. Delete `listings[<id>]` if present; otherwise report that it was not in the watchlist.
5. Write the file back using a full overwrite via `Write` (the file is small and a partial update would risk leaving the JSON half-formed).
6. Print the resulting watchlist state to the conversation as a short bullet list, one line per entry: `- <listing_id>: <note> (added <date>)`.
7. Remind the user to rerun `/build-dashboard` so the stars update in the rendered HTML.

Notes:
- Listing ids are the stable identifiers captured by `/search-cars` into the CSV `listing_id` column. For AutoTrader, this is the 15-digit numeric id after `/car-details/`. For other sources, it is the `{source}:{hash}` fallback. Do not accept composite keys like `42500_Testville`.
- Never write the watchlist under `${CLAUDE_PLUGIN_DATA}` - it is a per-project artefact, not a per-user setting, and belongs next to the dated CSV archive.
- Validate that the listing id is non-empty before writing. Fail loudly with a short message if the user runs `/watch-car add` without an id.
