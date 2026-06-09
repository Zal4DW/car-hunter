---
description: Data-backed help negotiating a car purchase with a dealer
argument-hint: "[listing id or describe the car, e.g. the blue RS in Leeds]"
allowed-tools: Read, Bash, Glob
---

Available profiles: !`ls "${CLAUDE_PLUGIN_DATA}/profiles/" 2>/dev/null || echo "(none yet - run /setup-car first)"`
Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Coach the user through negotiating a specific car using the `negotiation-coach` skill at `${CLAUDE_PLUGIN_ROOT}/skills/negotiation-coach/SKILL.md` - read it and follow it; it defines the evidence-pack script, the assessment structure, and the coaching playbook.

Profile resolution: a car named in $ARGUMENTS wins, then the active profile, then the single existing profile, then ask. If $ARGUMENTS contains a listing id, use it directly; if it describes the car instead, match it against the latest CSV in `{profile_name}-searches/` and confirm the match before building the brief.
