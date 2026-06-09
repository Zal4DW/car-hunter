---
description: Compare your tracked cars at a budget - "what can I get for 40k?"
argument-hint: "[budget and/or car names, e.g. 40k, or bmw vs audi at 45k]"
allowed-tools: Read, Bash, Glob
---

Available profiles: !`ls "${CLAUDE_PLUGIN_DATA}/profiles/" 2>/dev/null || echo "(none yet - run /setup-car first)"`
Active profile: !`cat "${CLAUDE_PLUGIN_DATA}/active-profile" 2>/dev/null || echo "(not set)"`

Answer "what can I get for £X?" across the cars the user tracks. Each car is scored by its own profile's regression, then the budget-sliced markets are compared side by side. Works with two or more cars - or a single car, where it compares what the budget buys across that car's variants and generations.

Follow these steps:

1. Resolve which cars to compare: cars named in $ARGUMENTS win; otherwise compare ALL profiles that have search data. Parse a budget from $ARGUMENTS ("40k" = 40000, "£37,500" = 37500); if none given and the user clearly wants a budget answer, ask - otherwise omit the budget to compare whole markets.
2. For each car, find the latest dated CSV in `{profile_name}-searches/` in the current workspace. If a car has no search data, say so and offer to run /search-cars for it - do not silently drop it from the comparison.
3. Run the comparison script with one `--car` per car (profile path and CSV path joined by a colon):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/compare_cars.py" \
     --car "${CLAUDE_PLUGIN_DATA}/profiles/{a}.json:{a}-searches/{a}-all-listings-{date}.csv" \
     --car "${CLAUDE_PLUGIN_DATA}/profiles/{b}.json:{b}-searches/{b}-all-listings-{date}.csv" \
     --budget {budget} --json
   ```
4. Present the answer as a compact markdown table, one row per car: listings in budget, newest year you can get, lowest mileage, typical example (median age/mileage/price), median % of RRP retained, and the best-value pick with a clickable link where available.
5. Close with the verdict the data supports: which car gets you the newest/freshest example for the money, which holds value best, and any standout individual deal. If snapshot dates differ between cars by more than a few days, mention the comparison is only as fresh as the oldest search.

Notes:
- If the budget is below every car's cheapest listing, report each car's entry point ("the market starts at £X") so the user knows what the budget needs to be.
- Different cars may have been searched on different dates - the script compares whatever CSVs you give it; freshness is your job to flag.
