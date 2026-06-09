---
description: Build or update the buyer intelligence dashboard for a tracked car
argument-hint: "[car name, if you track more than one]"
allowed-tools: Read, Write, Glob, Bash
---

Available profiles: !`ls "${CLAUDE_PLUGIN_DATA}/profiles/" 2>/dev/null || echo "(none yet - run /setup-car first)"`
Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Build the interactive dashboard using the `car-value-dashboard` skill at `${CLAUDE_PLUGIN_ROOT}/skills/car-value-dashboard/SKILL.md` - read it and follow it; it defines the builder invocation (including `--summary-json`) and how to present the key findings.

Profile resolution: a car named in $ARGUMENTS wins, then the active profile, then the single existing profile, then ask. Locate the latest dated CSV in `{profile_name}-searches/` in the current workspace; if none exists, tell the user to run /search-cars first.
