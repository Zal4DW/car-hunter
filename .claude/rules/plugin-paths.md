# Plugin Paths

## Use `${CLAUDE_PLUGIN_ROOT}` for in-plugin assets

All references to files that ship with the plugin (profiles, skills, scripts, reference data) must resolve through the `${CLAUDE_PLUGIN_ROOT}` environment variable. Never hardcode absolute paths like `/mnt/e/Development/Car-hunter/`.

**Good:**
- `${CLAUDE_PLUGIN_ROOT}/profiles/audi-etron-gt.json`
- `${CLAUDE_PLUGIN_ROOT}/skills/car-search/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py`

**Bad:**
- `/mnt/e/Development/Car-hunter/profiles/audi-etron-gt.json`
- `./profiles/audi-etron-gt.json` (breaks when the user's CWD is not the plugin root)

## Use the user's workspace for generated output

Search reports, CSV archives, and dashboard HTML are user artefacts, not plugin assets. Write them to the user's current workspace, not into `${CLAUDE_PLUGIN_ROOT}`:

- `{profile_name}-searches/{profile_name}-search-{YYYY-MM-DD}.md`
- `{profile_name}-searches/{profile_name}-all-listings-{YYYY-MM-DD}.csv`
- `{profile_name}-searches/{profile_name}-dashboard.html`

The `{profile_name}-searches/` folder is created in the user's working directory on first run.

## Why

- Plugins can be installed read-only or from a marketplace package. Writing into `${CLAUDE_PLUGIN_ROOT}` may fail or pollute the install.
- Generated artefacts are the user's data and should live with their other project files.
- Dated snapshots in the workspace enable volatility analysis across search runs without touching plugin internals.
