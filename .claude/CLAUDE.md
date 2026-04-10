# Car-hunter Plugin

A Claude Code plugin for tracking UK used car listings, detecting deals via multivariate regression, and generating buyer intelligence dashboards. Fully config-driven: every skill, command, and output reads from a car profile JSON.

## Repo layout

This repository is a **Claude Code plugin marketplace**. The plugin itself lives in a subdirectory so the same-repo marketplace manifest can source it.

```
Car-hunter/                              # marketplace repo root
├── .claude-plugin/marketplace.json      # marketplace manifest (points at ./car-hunter)
├── .claude/                             # repo-level dev rules (loaded by Claude Code)
├── .github/workflows/test.yml           # CI (pytest + coverage)
├── tests/                               # pytest harness (not shipped)
├── pyproject.toml, Makefile             # dev tooling
├── README.md, LICENSE                   # repo-level docs
└── car-hunter/                          # THE PLUGIN (shipped via marketplace)
    ├── .claude-plugin/plugin.json       # plugin manifest
    ├── commands/                        # slash commands
    ├── skills/                          # SKILL.md files
    ├── scripts/                         # Python builder + dashboard_lib
    └── docs/                            # profile schema reference
```

When Claude Code installs this plugin from the marketplace, `${CLAUDE_PLUGIN_ROOT}` resolves to the `car-hunter/` subdirectory (wherever the user's install cached it). Tests, CI, and dev tooling stay at the repo root and are never shipped.

## Components

- **Commands** (`car-hunter/commands/`): `/setup-car`, `/search-cars`, `/build-dashboard`
- **Skills** (`car-hunter/skills/`): `setup-car-profile`, `car-search`, `car-value-dashboard`
- **Builder** (`car-hunter/scripts/build_dashboard.py`): standalone Python script, no external libraries, generates self-contained HTML
- **Lib** (`car-hunter/scripts/dashboard_lib.py`): pure maths helpers extracted for unit testability

## Rules (always apply)

- [UK English](.claude/rules/uk-english.md)
- [Skill frontmatter](.claude/rules/skill-frontmatter.md)
- [Config-driven profiles](.claude/rules/config-driven-profiles.md)
- [Plugin paths](.claude/rules/plugin-paths.md)

## Workflow

1. `/setup-car` creates or updates a profile (conversational, uses `setup-car-profile` skill). Writes to `${CLAUDE_PLUGIN_DATA}/profiles/`.
2. `/search-cars` scrapes configured sources via browser MCP (WebFetch is blocked on most listing sites), deduplicates, writes a dated markdown report and CSV to `{profile_name}-searches/` in the user's workspace.
3. `/build-dashboard` runs `car-hunter/scripts/build_dashboard.py` over the latest CSV and profile to emit `{profile_name}-dashboard.html`.

## Conventions

- Profile JSON is the single source of truth. Never hardcode car-specific values (variants, colours, new prices, URLs) in skills or the builder.
- Three path locations, never confused (see [plugin-paths.md](rules/plugin-paths.md)):
  - `${CLAUDE_PLUGIN_ROOT}` - bundled, read-only plugin assets (scripts, skills, schema docs). At runtime this resolves to the `car-hunter/` subdir.
  - `${CLAUDE_PLUGIN_DATA}` - per-user plugin state, writable (profiles)
  - User's workspace - project artefacts (search reports, CSVs, dashboards)
- Profiles **must** be written to `${CLAUDE_PLUGIN_DATA}/profiles/`, never `${CLAUDE_PLUGIN_ROOT}/profiles/`. The plugin root is read-only on marketplace installs and wiped on every update.
- Dated snapshots: `{profile}-all-listings-{YYYY-MM-DD}.csv` enables volatility analysis between runs.
- No external Python libraries in `car-hunter/scripts/build_dashboard.py` - OLS via Gaussian elimination, Chart.js from CDN.
- Pure maths helpers live in `car-hunter/scripts/dashboard_lib.py` so they can be unit-tested without running the full builder.

## Version sync

Three files carry the version number and must stay in sync:
- `.claude-plugin/marketplace.json` - top-level marketplace manifest
- `car-hunter/.claude-plugin/plugin.json` - plugin manifest
- `README.md` if it mentions a version (currently does not)

Bump all three together. CI does not enforce this yet.
