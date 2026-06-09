---
description: Quick digest of what changed since the last search - new cars, removals, price drops
argument-hint: "[car name, if you track more than one]"
allowed-tools: Read, Bash, Glob
---

Available profiles: !`ls "${CLAUDE_PLUGIN_DATA}/profiles/" 2>/dev/null || echo "(none yet - run /setup-car first)"`
Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Answer "anything new, anything dropped in price?" without rebuilding the dashboard. This reads the dated snapshot CSVs that /search-cars has already saved - it does not scrape anything.

Follow these steps:

1. Resolve the profile: a car named in $ARGUMENTS wins, then the active profile, then the single existing profile, then ask.
2. Run the pulse script against the searches folder in the current workspace:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/market_pulse.py" \
     --profile "${CLAUDE_PLUGIN_DATA}/profiles/{profile_name}.json" \
     --dir "{profile_name}-searches" --json
   ```
3. Relay the digest conversationally: new arrivals (with prices and locations), removed listings, price drops (old -> new), and the median movement. Lead with the most actionable item - a meaningful price drop or a strong new arrival.
4. If the latest snapshot is older than 2 days, mention it and offer to run /search-cars for fresh data.
