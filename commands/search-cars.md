---
description: Search for used cars matching your active car profile
allowed-tools: WebSearch, WebFetch, Read, Write, Glob, Bash, mcp__Claude_in_Chrome__*
---

Search UK car listing websites for used cars matching the active car profile. Uses the car-search skill with config-driven search methodology.

Follow these steps:

1. Read the available profiles in `${CLAUDE_PLUGIN_ROOT}/profiles/` to find `.json` profile files.
2. If multiple profiles exist, ask the user which car to search for. If only one exists, use it.
3. Load the selected car profile JSON.
4. Read the skill file at `${CLAUDE_PLUGIN_ROOT}/skills/car-search/SKILL.md` for the full search process.
5. Use Claude in Chrome browser tools as the primary search method (WebFetch is blocked for car listing sites).
6. Build search URLs from the profile for each variant and each configured search site.
7. Search each source, extracting data points as defined in the skill.
8. Deduplicate listings that appear on multiple platforms.
9. Present results in a markdown table with direct links to each listing.
10. Save the search report and CSV data to the `{profile_name}-searches/` folder.
11. Compare against previous search reports for volatility analysis if available.

If $ARGUMENTS contains filter terms (e.g. "RS only", "under 60k", "blue"), apply those filters instead of the profile defaults.

If $ARGUMENTS contains a car name that matches a profile, use that profile directly without asking.
