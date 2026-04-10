---
description: Set up a new car profile or update an existing one
allowed-tools: Read, Write, Bash, AskUserQuestion
---

Create or update a car profile for the car-hunter plugin. The profile configures search URLs, spec options, variant tiers, and dashboard settings for a specific make and model.

Profiles live in the plugin's persistent user-data directory (`${CLAUDE_PLUGIN_DATA}/profiles/`), which survives plugin updates and is writable on marketplace installs. The bundled read-only `${CLAUDE_PLUGIN_ROOT}` is only used to load the setup skill and the schema reference.

Follow these steps:

1. Read the skill file at `${CLAUDE_PLUGIN_ROOT}/skills/setup-car-profile/SKILL.md` for the full setup process.
2. Ensure the data directory exists: `mkdir -p "${CLAUDE_PLUGIN_DATA}/profiles"`.
3. Check `${CLAUDE_PLUGIN_DATA}/profiles/` for existing profiles.
4. If $ARGUMENTS contains a car name, pre-populate where possible.
5. Walk the user through the interactive setup, gathering car identity, variants, generations, spec options, search preferences, and dashboard settings.
6. Write the completed profile to `${CLAUDE_PLUGIN_DATA}/profiles/{profile-name}.json`.
7. Generate the spec reference file at `${CLAUDE_PLUGIN_DATA}/references/{profile-name}-specs.md`.
8. Offer to run the first search.
