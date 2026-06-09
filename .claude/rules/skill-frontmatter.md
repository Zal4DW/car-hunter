# Skill Frontmatter

Every skill lives at `skills/{skill-name}/SKILL.md` and must open with YAML frontmatter. These rules are enforced in CI by `tests/repo/test_plugin_hygiene.py`.

## Required fields

### `name`
- Lowercase kebab-case only: `car-search`, not `Car-Search` or `car_search`
- Max 64 characters
- Must match the folder name

### `description`
- Max **1024 characters** (repo convention; the platform cap is 1536 combined with `when_to_use`)
- Must describe **what** the skill does **and when** it should activate
- Include concrete trigger phrases the user is likely to say ("search for cars", "update the dashboard", etc.) - this is how Claude discovers the skill
- Be specific, not generic. Bad: `Searches for cars`. Good: `Search UK car listing sites (AutoTrader, Cazoo, Cinch) for used cars matching an active car profile, deduplicate across sources, and produce a cited markdown report plus CSV.`

## Optional fields

### `allowed-tools`
- Restricts which tools Claude can use while the skill is active
- Either a comma/space-separated string (`Read, Grep`) or a YAML list - both are supported by the platform
- Only needed to constrain tool access; omit to allow all

### `context` and `agent`
- `context: fork` runs the skill in a forked subagent context; `agent` picks the subagent type
- Use for skills that do heavy, self-contained work (like the search capture)

### `argument-hint`
- Autocomplete hint for arguments, e.g. `[car name]`

## Fields that do NOT belong on skills

Skills use **model-based activation**, not user search. Do not add:
- `version` (not part of the skill frontmatter spec - track versions in plugin.json)
- `usage` (belongs on slash commands and docs)
- `tags` (belongs on marketplace entries and docs)
- `model` (inherited from session)

## Skill body structure

1. H1 title
2. One-paragraph purpose statement
3. **When to Use** - bullet list of trigger scenarios (or fold into the purpose statement)
4. **Prerequisites** - profiles, data files, MCP servers required
5. Process steps in order, with clear headings
6. **Output** section - what the skill produces and where files land
7. **Important Notes** - gotchas, edge cases

Keep skills under ~250 lines (CI-enforced). If longer, move reference material to `docs/` and link from SKILL.md.
