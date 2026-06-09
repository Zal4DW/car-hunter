---
description: Set up a new car profile or update an existing one
argument-hint: "[make and model, e.g. BMW i4]"
allowed-tools: Read, Write, Bash, Glob, WebSearch, AskUserQuestion
---

Existing profiles: !`ls "${CLAUDE_PLUGIN_DATA}/profiles/" 2>/dev/null || echo "(none yet)"`
Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Create or update a car profile using the `setup-car-profile` skill at `${CLAUDE_PLUGIN_ROOT}/skills/setup-car-profile/SKILL.md` - read it and follow it; it defines the quick-setup flow, validation, and file locations.

If $ARGUMENTS names a car, pre-populate from it (and if it matches an existing profile, switch to update mode for that profile). Prefer the quick setup path unless the user asks for full control.
