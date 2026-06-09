---
description: Search for used cars matching your active car profile
argument-hint: "[car name and/or filters, e.g. audi under 60k]"
allowed-tools: Read, Write, Glob, Bash, WebSearch, WebFetch, mcp__Claude_in_Chrome__*
---

Available profiles: !`ls "${CLAUDE_PLUGIN_DATA}/profiles/" 2>/dev/null || echo "(none yet - run /setup-car first)"`
Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Search UK car listing websites using the `car-search` skill at `${CLAUDE_PLUGIN_ROOT}/skills/car-search/SKILL.md` - read it and follow it; it defines the capture format, the ingest script invocation, and the report format.

Profile resolution: a car named in $ARGUMENTS wins, then the active profile, then the single existing profile, then ask. If $ARGUMENTS contains filter terms (e.g. "RS only", "under 60k", "blue"), apply those instead of the profile defaults for this run.
