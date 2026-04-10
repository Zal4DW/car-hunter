# car-hunter

Search UK car listings, track prices over time, and build buyer intelligence dashboards with regression-based value scoring. Works with any car model via config-driven car profiles.

## What it does

Searches AutoTrader, Cazoo, Cinch, CarWow, manufacturer approved used programmes, and major dealer groups for used cars matching your profile. Tracks prices across snapshots, detects deals via multivariate regression, and generates interactive HTML dashboards with depreciation curves, spec premium analysis, and negotiation radar.

## Components

| Component | Name | Purpose |
|-----------|------|---------|
| Command | `/setup-car` | Create or update a car profile for a make/model |
| Command | `/search-cars` | Search all listing sites for your tracked car |
| Command | `/build-dashboard` | Build/update the buyer intelligence dashboard |
| Skill | `setup-car-profile` | Interactive profile creation with full configuration |
| Skill | `car-search` | Config-driven search methodology and data extraction |
| Skill | `car-value-dashboard` | Dashboard builder with regression modelling |
| Script | `scripts/build_dashboard.py` | Python builder: profile + CSV -> HTML dashboard |
| Profiles | `profiles/*.json` | Car profile configurations |

## Quick start

1. Run `/setup-car` to create a profile for the car you want to track
2. Run `/search-cars` to search all configured listing sites
3. Run `/build-dashboard` to generate the interactive analytics dashboard

## Car profiles

Each profile defines: make/model, variant tiers, generation detection, spec options with search terms and regression weights, search URLs, filter defaults, and dashboard theming. Profiles are stored as JSON in the `profiles/` folder.

Run `/setup-car` to create your first profile interactively. The schema is documented in `profiles/car-profile-schema.md`.

## Dashboard builder

The Python builder (`scripts/build_dashboard.py`) is a standalone script that reads a car profile and CSV data file, then generates a self-contained HTML dashboard. No external Python libraries required.

```bash
python3 scripts/build_dashboard.py --profile profiles/your-car.json --csv your-car-searches/your-car-all-listings-YYYY-MM-DD.csv
```

## Default sources (UK)

AutoTrader UK (primary), Cazoo, Cinch, CarWow, Motorpoint, manufacturer approved used programmes, and configurable dealer groups. Additional sources can be added per profile.

## How pages are fetched

Most major UK car listing sites block `WebFetch` and plain HTTP scrapers. Car-hunter is designed around the [Claude in Chrome](https://www.anthropic.com/news/claude-for-chrome) browser extension, which drives a real signed-in Chrome session to navigate AutoTrader, Cazoo, and the rest, extract listing details (including the "View all spec and features" panel), and follow deep links to individual cars.

**Requirements:**

- Claude Desktop or Claude Code with the Claude in Chrome extension installed and authorised
- The `mcp__Claude_in_Chrome__*` tools available to the `car-search` skill
- A Chrome window open when you run `/search-cars`

`WebSearch` is used as a best-effort fallback if the browser is unavailable, but results are much thinner and spec lists cannot be extracted reliably.

## Licence

Car Hunter is released under the [Creative Commons Attribution-NonCommercial 4.0 International Licence (CC BY-NC 4.0)](LICENSE). You are free to use, share, and adapt it for personal and non-commercial use, with attribution. Commercial use - including reselling, integrating into a paid service, or running it on behalf of a dealership or broker - is not permitted. See [LICENSE](LICENSE) for the full terms and disclaimers.

Car Hunter is a buyer-intelligence aid, not financial or purchase advice. Value scores and depreciation estimates are statistical approximations - always verify listings and inspect vehicles before buying.
