# Skill Frontmatter

Every skill lives at `skills/{skill-name}/SKILL.md` and must open with YAML frontmatter.

## Required fields

### `name`
- Lowercase kebab-case only: `car-search`, not `Car-Search` or `car_search`
- Max 64 characters
- Must match the folder name

### `description`
- Max **1024 characters**
- Must describe **what** the skill does **and when** it should activate
- Include concrete trigger phrases the user is likely to say ("search for cars", "update the dashboard", etc.) - this is how Claude discovers the skill
- Be specific, not generic. Bad: `Searches for cars`. Good: `Search UK car listing sites (AutoTrader, Cazoo, Cinch) for used cars matching an active car profile, deduplicate across sources, and produce a cited markdown report plus CSV.`

## Optional fields

### `allowed-tools`
- Comma-separated list restricting which tools Claude can use while the skill is active
- Example: `Read, Write, Glob, Bash, WebSearch, WebFetch, mcp__Claude_in_Chrome__*`
- Only needed if you want to constrain tool access; omit to allow all

### `version`
- Semver string (e.g. `1.0.0`)

## Fields that do NOT belong on skills

Skills use **model-based activation**, not user search. Do not add:
- `usage` (belongs on slash commands and docs)
- `tags` (belongs on slash commands and docs)
- `model` (inherited from session)

## Skill body structure

1. H1 title
2. One-paragraph purpose statement
3. **When to Use** - bullet list of trigger scenarios
4. **Prerequisites** - profiles, data files, MCP servers required
5. Process steps in order, with clear headings
6. **Output** section - what the skill produces and where files land
7. **Important Notes** - gotchas, edge cases, deduplication rules

Keep skills under ~250 lines. If longer, move reference material to `skills/{name}/docs/` and link from SKILL.md.
