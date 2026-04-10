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
- Three path locations, never confused (see [plugin-paths.md](rules/plugin-paths.md)):
  - `${CLAUDE_PLUGIN_ROOT}` - bundled, read-only (scripts, skills, schema docs)
  - `${CLAUDE_PLUGIN_DATA}` - per-user plugin state, writable (profiles)
  - User's workspace - project artefacts (search reports, CSVs, dashboards)
- Profiles **must** be written to `${CLAUDE_PLUGIN_DATA}/profiles/`, never `${CLAUDE_PLUGIN_ROOT}/profiles/`. The plugin root is read-only on marketplace installs and wiped on every update.
- Dated snapshots: `{profile}-all-listings-{YYYY-MM-DD}.csv` enables volatility analysis between runs.
- No external Python libraries in `scripts/build_dashboard.py` - OLS via Gaussian elimination, Chart.js from CDN.
- Pure maths helpers live in `scripts/dashboard_lib.py` so they can be unit-tested without running the full builder.
