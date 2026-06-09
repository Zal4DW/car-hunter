# Car-hunter Plugin

A Claude Code plugin for tracking UK used car listings, detecting deals via multivariate regression, and generating buyer intelligence dashboards. Fully config-driven: every skill, command, and output reads from a car profile JSON.

## Repo layout

This repository is a **Claude Code plugin marketplace**. The plugin itself lives in a subdirectory so the same-repo marketplace manifest can source it.

```text
car-hunter/                              # marketplace repo root
├── .claude-plugin/marketplace.json      # marketplace manifest (points at ./car-hunter)
├── .claude/                             # repo-level dev rules (loaded by Claude Code)
├── .github/workflows/test.yml           # CI (pytest + coverage + hygiene gates)
├── tests/                               # pytest harness (not shipped)
│   └── repo/                            # version-sync + frontmatter lint gates
├── pyproject.toml, Makefile             # dev tooling
├── README.md, LICENSE                   # repo-level docs
└── car-hunter/                          # THE PLUGIN subdir (shipped via marketplace)
    ├── .claude-plugin/plugin.json       # plugin manifest
    ├── commands/                        # slash commands (thin - defer to skills)
    ├── skills/                          # SKILL.md files (the process truth)
    ├── scripts/                         # Python pipeline (see Components)
    └── docs/                            # profile schema reference + examples/
```

When Claude Code installs this plugin from the marketplace, `${CLAUDE_PLUGIN_ROOT}` resolves to the `car-hunter/` subdirectory (wherever the user's installation cache stores it). Tests, CI, and dev tooling stay at the repo root and are never shipped.

## Components

- **Commands** (`car-hunter/commands/`): `/setup-car`, `/search-cars`, `/build-dashboard`, `/car-pulse`, `/compare-cars`, `/help-me-negotiate`, `/use-car`, `/watch-car`. Commands are deliberately thin: they inject live profile context via `` !`command` `` and defer the process to the matching skill. Never duplicate skill steps inside a command.
- **Skills** (`car-hunter/skills/`): `setup-car-profile`, `car-search`, `car-value-dashboard`, `negotiation-coach`. Skills are the single source of process truth.
- **Ingest** (`car-hunter/scripts/ingest_listings.py` + `ingest_lib.py`): turns the raw capture JSON written by the search skill into the dated CSV + capture manifest. ALL derived maths (listing ids, reg dates, ages, depreciation, generation detection, cross-source dedup) happens here - the language model only extracts what listing pages say.
- **Builder** (`car-hunter/scripts/build_dashboard.py`): generates the self-contained HTML dashboard. Also provides `--validate-profile` (used by setup) and `--summary-json` (machine-readable findings for the skill layer).
- **Pulse** (`car-hunter/scripts/market_pulse.py`): quick what-changed digest by diffing the two latest snapshot CSVs - no dashboard rebuild needed.
- **Compare** (`car-hunter/scripts/compare_cars.py` + `compare_lib.py`): budget-anchored cross-profile comparison ("what can I get for £40k?"). Each car is scored by its own profile's regression, then the budget-sliced markets are laid side by side.
- **Negotiation** (`car-hunter/scripts/negotiation_brief.py` + `negotiation_lib.py`): evidence pack for haggling over one listing - market position, price-drop history, comparables, supply, offer anchors. The `negotiation-coach` skill turns the numbers into strategy.
- **Lib** (`car-hunter/scripts/dashboard_lib.py`): pure maths helpers extracted for unit testability.

## Rules (always apply)

- [UK English](.claude/rules/uk-english.md)
- [Skill frontmatter](.claude/rules/skill-frontmatter.md)
- [Config-driven profiles](.claude/rules/config-driven-profiles.md)
- [Plugin paths](.claude/rules/plugin-paths.md)

## Workflow

1. `/setup-car` creates or updates a profile (quick setup by default: four questions, Claude researches the rest, user confirms). Writes to `${CLAUDE_PLUGIN_DATA}/profiles/`, validates with `--validate-profile`, and sets `${CLAUDE_PLUGIN_DATA}/active-profile`.
2. `/search-cars` scrapes configured sources via browser MCP (WebFetch is blocked on most listing sites), writes a **raw capture JSON**, then runs `ingest_listings.py` which emits the dated CSV + capture manifest into `{profile_name}-searches/` in the user's workspace. A dated markdown report is written alongside.
3. `/build-dashboard` runs `build_dashboard.py` over the latest CSV and profile to emit `{profile_name}-dashboard.html` plus a summary JSON the skill presents from.
4. `/car-pulse` answers "what changed since last search" from the snapshot archive without a rebuild.
5. `/compare-cars {budget}` answers "what can I get for £X" across tracked cars (or within one car's variants).
6. Multi-car: one profile per car; `${CLAUDE_PLUGIN_DATA}/active-profile` holds the default; `/use-car` switches it; naming a car in any command's arguments overrides it for that run.

## Conventions

- Profile JSON is the single source of truth. Never hardcode car-specific values (variants, colours, new prices, URLs) in skills or the builder.
- The LLM never does arithmetic or hand-formats CSV. Extraction happens in skills; derivation happens in `ingest_lib.py`/`dashboard_lib.py` where it is exact and tested.
- Three path locations, never confused (see [plugin-paths.md](rules/plugin-paths.md)):
  - `${CLAUDE_PLUGIN_ROOT}` - bundled, read-only plugin assets (scripts, skills, schema docs, example profiles). At runtime this resolves to the `car-hunter/` subdir.
  - `${CLAUDE_PLUGIN_DATA}` - per-user plugin state, writable (profiles, active-profile pointer, spec references)
  - User's workspace - project artefacts (raw captures, search reports, CSVs, dashboards, watchlists)
- Profiles **must** be written to `${CLAUDE_PLUGIN_DATA}/profiles/`, never `${CLAUDE_PLUGIN_ROOT}/profiles/`. The plugin root is read-only on marketplace installs and wiped on every update.
- Dated snapshots: `{profile}-all-listings-{YYYY-MM-DD}.csv` enables volatility analysis between runs. Builds are anchored to the CSV filename date, not the wall clock.
- No external Python libraries in any `car-hunter/scripts/` file - OLS via Gaussian elimination, Chart.js from CDN.
- Bad CSV rows are skipped with visible warnings (stdout AND dashboard banner), never fatal; missing files and missing columns are fatal with actionable messages.
- Pure helpers live in `dashboard_lib.py`/`ingest_lib.py` so they can be unit-tested without running the full pipeline.

## Version sync

Three files carry the version number and must stay in sync:
- `.claude-plugin/marketplace.json` - top-level manifest AND its plugin entry
- `car-hunter/.claude-plugin/plugin.json` - plugin manifest
- `README.md` if it mentions a version (currently does not)

CI enforces this via `tests/repo/test_plugin_hygiene.py`, alongside skill frontmatter linting and example-profile validation.
