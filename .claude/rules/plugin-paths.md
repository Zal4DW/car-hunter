# Plugin Paths

Car Hunter uses three distinct storage locations. Picking the wrong one leads to data loss on plugin updates, write failures on marketplace installs, or user data polluting the plugin install.

## The three locations

### 1. `${CLAUDE_PLUGIN_ROOT}` - bundled, read-only

The absolute path to the plugin's installation directory. Contains everything that ships with the plugin:

- `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md`
- `${CLAUDE_PLUGIN_ROOT}/commands/*.md`
- `${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py`
- `${CLAUDE_PLUGIN_ROOT}/scripts/dashboard_lib.py`
- `${CLAUDE_PLUGIN_ROOT}/docs/car-profile-schema.md` (schema reference)

At runtime `${CLAUDE_PLUGIN_ROOT}` resolves to the `car-hunter/` subdirectory inside the repo (or wherever Claude Code cached the install). Repo-relative paths during development are `car-hunter/skills/`, `car-hunter/scripts/`, etc. Skills and commands should always use the `${CLAUDE_PLUGIN_ROOT}` variable, never hardcoded repo-relative paths, so they work identically at dev time and after install.

**Rules:**
- Treat as read-only. On marketplace installs the plugin cache is replaced on every update, so anything written here is lost.
- Never write user data here. Never write profiles, search results, CSVs, or dashboards here.
- Use it only to reference bundled assets: scripts, skills, agents, hooks, schema docs, example templates.

### 2. `${CLAUDE_PLUGIN_DATA}` - per-user plugin state, writable, persistent

A plugin-private directory that survives plugin updates. Claude Code creates it automatically the first time it is referenced and resolves it to `~/.claude/plugins/data/{plugin-id}/`. It is deleted when the plugin is uninstalled from the last scope (unless `--keep-data` is passed).

**What lives here:**
- `${CLAUDE_PLUGIN_DATA}/profiles/{profile-name}.json` - user's car profiles
- `${CLAUDE_PLUGIN_DATA}/references/{profile-name}-specs.md` - generated spec identification guides

**Rules:**
- This is the **only** writable location for plugin-private user state.
- Profiles live here because they are per-user settings, not project artefacts. A user's Audi profile should be available regardless of which directory they run Claude from.
- Ensure the subdirectory exists before writing: `mkdir -p "${CLAUDE_PLUGIN_DATA}/profiles"`. `${CLAUDE_PLUGIN_DATA}` itself is auto-created but subdirectories inside it are not.
- Do not put outputs the user wants to browse (reports, HTML dashboards) here - they belong in the user's workspace instead.

### 3. The user's current workspace - project artefacts

The directory Claude was launched from. This is where outputs tied to a specific "search campaign" belong - files the user wants to see, compare, and archive with their other project files.

**What lives here:**
- `{profile_name}-searches/{profile_name}-search-{YYYY-MM-DD}.md` - dated markdown reports
- `{profile_name}-searches/{profile_name}-all-listings-{YYYY-MM-DD}.csv` - dated CSV archives
- `{profile_name}-searches/{profile_name}-dashboard.html` - generated dashboard

**Rules:**
- Create the `{profile_name}-searches/` folder lazily on first search.
- Never write to the user's workspace root - always inside a namespaced subfolder.
- The dashboard HTML is self-contained (all data embedded, CDN for Chart.js) so it travels with the user's files.

## Common mistakes to avoid

| Mistake | Why it breaks | Correct location |
|---|---|---|
| Writing profiles to `${CLAUDE_PLUGIN_ROOT}/profiles/` | Plugin root is read-only on marketplace installs; lost on update | `${CLAUDE_PLUGIN_DATA}/profiles/` |
| Writing dashboards to `${CLAUDE_PLUGIN_DATA}` | User can't find them; hidden in dotfiles | `{profile_name}-searches/` in workspace |
| Hardcoding `/home/user/` or `/mnt/...` paths | Breaks on every other machine | Always use the env vars above |
| Reading the script from `./scripts/` (relative) | Breaks when user's cwd is not the plugin root | `${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py` |
| Passing `profiles/foo.json` as a relative path to the builder | Breaks when cwd is the user's workspace, not the plugin | `"${CLAUDE_PLUGIN_DATA}/profiles/foo.json"` (absolute) |

## Quick reference

```bash
# Read bundled asset (read-only)
cat "${CLAUDE_PLUGIN_ROOT}/docs/car-profile-schema.md"

# Write user profile (persistent, per-user)
mkdir -p "${CLAUDE_PLUGIN_DATA}/profiles"
echo "$PROFILE_JSON" > "${CLAUDE_PLUGIN_DATA}/profiles/audi-etron-gt.json"

# Write project artefact (visible in the user's workspace)
mkdir -p audi-etron-gt-searches
# ... write report/csv/html ...

# Invoke builder with absolute paths for both bundled script and persistent profile
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py" \
  --profile "${CLAUDE_PLUGIN_DATA}/profiles/audi-etron-gt.json" \
  --csv audi-etron-gt-searches/audi-etron-gt-all-listings-2026-04-10.csv
```

## Why three locations, not two?

Other Claude Code plugins often get by with just `${CLAUDE_PLUGIN_ROOT}` + workspace. Car Hunter needs three because profiles are **user settings** (not project state) and **persistent** (not bundled). Mixing them into either of the other two locations causes pain:

- Profile-in-workspace means the user has to re-create it every time they cd elsewhere. Bad UX.
- Profile-in-plugin-root means writes fail on marketplace installs and get wiped on updates. Broken.
- Only `${CLAUDE_PLUGIN_DATA}` gives the "works from any directory, survives updates, writable" combination.
