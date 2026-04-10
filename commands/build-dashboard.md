---
description: Build or update the buyer intelligence dashboard for a tracked car
allowed-tools: Read, Write, Bash
---

Build or update an interactive depreciation analysis dashboard for a tracked car. Uses regression modelling, value scoring, and Chart.js visualisations.

Follow these steps:

1. Read the available profiles in `${CLAUDE_PLUGIN_ROOT}/profiles/` to find `.json` profile files.
2. If multiple profiles exist, ask the user which car to build the dashboard for.
3. Load the selected car profile JSON.
4. Read the skill file at `${CLAUDE_PLUGIN_ROOT}/skills/car-value-dashboard/SKILL.md` for the full build process.
5. Locate the latest CSV data file in the `{profile_name}-searches/` folder.
6. Run the builder: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py --profile <profile.json> --csv <latest.csv>`. The script is fully config-driven and does not need to be edited or regenerated per profile.
7. Present key findings (R-squared, top deals, spec premiums, flattening point).

If $ARGUMENTS contains a car name that matches a profile, use that profile directly.
