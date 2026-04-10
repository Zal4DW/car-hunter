---
description: Set up a new car profile or update an existing one
allowed-tools: Read, Write, AskUserQuestion
---

Create or update a car profile for the car-hunter plugin. The profile configures search URLs, spec options, variant tiers, and dashboard settings for a specific make and model.

Follow these steps:

1. Read the skill file at `${CLAUDE_PLUGIN_ROOT}/skills/setup-car-profile/SKILL.md` for the full setup process.
2. Check `${CLAUDE_PLUGIN_ROOT}/profiles/` for existing profiles.
3. If $ARGUMENTS contains a car name, pre-populate where possible.
4. Walk the user through the interactive setup, gathering car identity, variants, generations, spec options, search preferences, and dashboard settings.
5. Write the completed profile to `${CLAUDE_PLUGIN_ROOT}/profiles/{profile-name}.json`.
6. Generate the spec reference file.
7. Offer to run the first search.
