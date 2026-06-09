---
description: Switch which car profile the other commands use by default
argument-hint: "<car name, e.g. bmw-i4>"
allowed-tools: Read, Write, Bash, Glob
---

Available profiles: !`ls "${CLAUDE_PLUGIN_DATA}/profiles/" 2>/dev/null || echo "(none yet - run /setup-car first)"`
Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Set the active car profile. The active profile is what `/search-cars`, `/build-dashboard`, and `/car-pulse` use when no car is named.

Follow these steps:

1. Match $ARGUMENTS against the available profiles (by filename, `profile_name`, `display_name`, or `make` - case-insensitive, partial matches fine if unambiguous).
2. If $ARGUMENTS is empty or ambiguous, list the profiles with their display names and ask which one.
3. Write the bare profile name (no extension, no newline padding) to `${CLAUDE_PLUGIN_DATA}/active-profile`:
   `echo "{profile-name}" > "${CLAUDE_PLUGIN_DATA}/active-profile"`
4. Confirm: "Active profile is now {display_name}. /search-cars and /build-dashboard will use it by default."
