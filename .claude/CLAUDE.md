# Car-hunter Plugin

A Claude Code plugin for tracking UK used car listings, detecting deals via multivariate regression, and generating buyer intelligence dashboards. Fully config-driven: every skill, command, and output reads from a car profile JSON in `profiles/`.

## Components

- **Commands** (`commands/`): `/setup-car`, `/search-cars`, `/build-dashboard`
- **Skills** (`skills/`): `setup-car-profile`, `car-search`, `car-value-dashboard`
- **Profiles** (`profiles/*.json`): car configurations (make/model, variants, specs, regression weights, dashboard theme)
- **Builder** (`scripts/build_dashboard.py`): standalone Python script, no external libraries, generates self-contained HTML

## Rules (always apply)

- [UK English](.claude/rules/uk-english.md)
- [Skill frontmatter](.claude/rules/skill-frontmatter.md)
- [Config-driven profiles](.claude/rules/config-driven-profiles.md)
- [Plugin paths](.claude/rules/plugin-paths.md)

## Workflow

1. `/setup-car` creates or updates a profile (conversational, uses `setup-car-profile` skill)
2. `/search-cars` scrapes configured sources via browser MCP (WebFetch is blocked on most listing sites), deduplicates, writes a dated markdown report and CSV to `{profile_name}-searches/`
3. `/build-dashboard` runs `scripts/build_dashboard.py` over the latest CSV and profile to emit `{profile_name}-dashboard.html`

## Conventions

- Profile JSON is the single source of truth. Never hardcode car-specific values (variants, colours, new prices, URLs) in skills or the builder.
- All in-plugin asset paths use `${CLAUDE_PLUGIN_ROOT}`, never absolute paths.
- Dated snapshots: `{profile}-all-listings-{YYYY-MM-DD}.csv` enables volatility analysis between runs.
- No external Python libraries in `scripts/build_dashboard.py` - OLS via Gaussian elimination, Chart.js from CDN.
