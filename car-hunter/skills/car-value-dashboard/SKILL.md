---
name: car-value-dashboard
description: >
  Build or update an interactive depreciation analysis dashboard for car listings.
  This skill should be used when the user asks to "update the dashboard",
  "rebuild the depreciation dashboard", "analyse car values",
  "show me the depreciation curve", "update car value analysis",
  "build the dashboard", "show me the deals", "which cars are good value",
  "what's the best value [car name]", "find undervalued cars", or any
  request related to analysing pricing, depreciation, or value retention
  for a tracked car. Config-driven: reads the active car profile.
---

# Car Value Dashboard - Buyer Intelligence

Build or update an interactive HTML dashboard that analyses car listings to help make informed purchase decisions. Uses multivariate regression to score value, identify negotiation opportunities, and visualise depreciation curves. Fully config-driven from a car profile.

## When to Use

- User asks to update or rebuild the depreciation/value dashboard
- User asks for depreciation analysis on their tracked car
- User wants to understand how age, mileage, or options affect values
- After running the `car-search` skill, to visualise the collected data

For a quick "what changed since last search" answer without a full rebuild, use `/car-pulse` instead.

## Prerequisites

1. A car profile in `${CLAUDE_PLUGIN_DATA}/profiles/` (created via `setup-car-profile`)
2. A CSV data file produced by the `car-search` skill, in `{profile_name}-searches/` in the user's workspace

Resolve the profile the same way as the search skill: named car in the request > `${CLAUDE_PLUGIN_DATA}/active-profile` > single existing profile > ask.

## Build

Run the bundled builder over the **latest** dated CSV. Never copy, edit, or regenerate the script per profile:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py" \
  --profile "${CLAUDE_PLUGIN_DATA}/profiles/{profile_name}.json" \
  --csv "{profile_name}-searches/{profile_name}-all-listings-{YYYY-MM-DD}.csv" \
  --summary-json "{profile_name}-searches/{profile_name}-summary.json"
```

The builder:

1. Validates the profile and loads the CSV (bad rows are skipped with warnings, not fatal)
2. Globs every dated snapshot CSV in the folder and diffs the latest two by `listing_id` for Market Pulse (new / removed / price drops) and a 28-day rolling time series
3. Anchors the build date to the date in the CSV filename, so rebuilding a day after the search still diffs correctly (`--date` overrides)
4. Runs multivariate OLS regression (intercept, age_months, mileage, spec_score, one dummy per variant tier > 0; spec_score weights come from `profile.spec_options`)
5. Computes per-listing `predicted_price`, `value_deviation`, `value_deviation_pct`, spec premiums (mean residual with vs without each option, min 3 each side), and per-variant quadratic depreciation curves with flattening points
6. Reads the watchlist (`{profile_name}-watchlist.json`) and capture manifest (`{profile_name}-capture-{date}.json`) if present
7. Writes the self-contained dashboard HTML and the run summary JSON

Only cars aged >= 6 months enter the regression; brand-new stock is excluded from the table. If the model is unreliable (too few rows, collinear features), the builder embeds a visible warning banner in the dashboard - mention it to the user.

## Present key findings from the summary JSON

Read the `--summary-json` file rather than parsing stdout. It contains: regression R-squared and row count, the top five deals (listing id, variant, price vs predicted, deviation %), spec premiums, per-variant flattening points, the market pulse counts, capture status, and any data warnings. Summarise for the user:

- How well the model fits (R-squared) and on how many cars
- The top 2-3 genuine deals with links and what makes them cheap
- Which options actually hold value (spec premiums)
- The depreciation sweet spot (flattening month) per variant
- What changed since the last run (pulse), and any warnings verbatim

## Dashboard contents (for reference)

Six Chart.js charts (market activity 28-day, depreciation curve with flattening annotation, deal score lollipops, spec premiums, negotiation radar of days-listed vs deviation, price vs mileage with trendline), a Market Pulse panel, KPI row, capture badge (green/amber/red from the manifest, grey if missing), and a sortable, filterable table of every listing. Filters: variant, generation, mileage, budget, value rating, watchlist.

Stars clicked in the dashboard persist in the browser via localStorage and survive rebuilds; the "Sync watchlist" button copies a `/watch-car sync {...}` command so the user can persist stars to the on-disk watchlist through Claude.

All theming, filter options, and labels come from `profile.dashboard` and `profile.variants[].colour` - never hardcode them.

## Output Files

All artefacts live in `{profile_name}-searches/` in the user's workspace:

1. `{profile_name}-dashboard.html` - self-contained, opens in a browser
2. `{profile_name}-summary.json` - machine-readable run summary
3. The dated CSV archive the builder read from

## Important Notes

- If the latest CSV is more than 2 days old, offer to run `car-search` first
- Snapshot diffing is keyed on the stable `listing_id` column - rows without ids opt out
- Dep/yr shows N/A for cars under 6 months old to avoid absurd annualised figures
- Use UK English throughout (organisation, colour, analyse, etc.)
