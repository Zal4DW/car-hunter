---
name: setup-car-profile
description: >
  This skill should be used when the user asks to "set up a car search",
  "create a car profile", "add a new car to track", "track a second car",
  "configure car hunter", "set up car-hunter", "edit my car profile",
  "change my search preferences", "update my car profile", "I want to
  search for a [car name]", or any request to configure which car model
  they want to track on the used market. Creates or updates a car profile
  JSON that configures all other car-hunter skills - search, dashboard,
  and analysis. Supports multiple profiles (e.g. a BMW and an Audi
  tracked side by side).
---

# Setup Car Profile

Create or update a car profile that configures the entire car-hunter plugin for a specific make and model. The profile drives the search skill, CSV schema, dashboard builder, and all analytical features. Users can hold any number of profiles - one per car they are hunting.

## Profile Location

Profiles are **user data**, not bundled plugin assets. Write them to:

```
${CLAUDE_PLUGIN_DATA}/profiles/{profile-name}.json
```

This directory is writable, persists across plugin updates, and is per-user. **Never write profiles to `${CLAUDE_PLUGIN_ROOT}/profiles/`** - the plugin root is read-only on marketplace installs and wiped on update.

The schema is documented in `${CLAUDE_PLUGIN_ROOT}/docs/car-profile-schema.md`. Complete, valid example profiles live in `${CLAUDE_PLUGIN_ROOT}/docs/examples/` - use them as templates.

## Quick setup (default)

Most users should not face a nine-step interview. Ask only the four things that cannot be derived, using AskUserQuestion where it fits:

1. **The car**: make and model (e.g. "BMW i4", "Audi e-tron GT").
2. **Budget and mileage caps**: maximum price and maximum mileage.
3. **Location**: home postcode and how far they will travel.
4. **Must-have options**: which extras genuinely matter to them (suggest the common ones: premium audio, panoramic roof, head-up display, adaptive suspension, performance/technology packs).

Then build the rest yourself:

- Start from the closest bundled example in `${CLAUDE_PLUGIN_ROOT}/docs/examples/` (copy its structure, not its car-specific values, unless it IS the same car).
- Research the car's variants, tiers, generations, and launch RRPs using your own knowledge plus WebSearch to confirm. Assign tier 0 to the base variant, ascending for performance trims, and a chart colour per variant.
- Use the standard UK reg-date mapping from the examples (it is the same for every UK car).
- Default the remaining search filters and dashboard settings from the example template.
- Enable `listing_id_date_encoding` (it applies to all UK AutoTrader listings).

Present a compact summary of what you derived (variants, tiers, RRPs per generation, spec options with weights) and ask the user to confirm or correct it **before** writing the file. RRPs matter most - flag that depreciation maths depends on them.

## Detailed setup (on request)

If the user wants full control, or the quick path hits a car you cannot research confidently, walk through each schema section in order: identity, variants, generations and RRPs, spec options (key, label, search_terms, weight, highlight), search preferences, search URLs, dashboard preferences. The schema doc lists every field.

## Writing and validating

1. Ensure the directory exists: `mkdir -p "${CLAUDE_PLUGIN_DATA}/profiles"`.
2. Write the profile to `${CLAUDE_PLUGIN_DATA}/profiles/{profile-name}.json`.
3. **Validate immediately** - schema mistakes must surface now, not days later at dashboard time:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build_dashboard.py" \
     --profile "${CLAUDE_PLUGIN_DATA}/profiles/{profile-name}.json" \
     --validate-profile
   ```
   If validation fails, fix the profile and re-run before telling the user it is done.
4. Set this profile as the active one so other commands stop asking:
   ```bash
   echo "{profile-name}" > "${CLAUDE_PLUGIN_DATA}/active-profile"
   ```
5. Generate `${CLAUDE_PLUGIN_DATA}/references/{profile-name}-specs.md` with human-readable spec identification guidance derived from spec_options and search_terms.
6. Offer to run the first search immediately.

## Multiple cars

Each car gets its own profile, its own `{profile-name}-searches/` folder, and its own dashboard - they never share data. To track a BMW and an Audi:

- Run this skill once per car.
- The **active profile** (`${CLAUDE_PLUGIN_DATA}/active-profile`) decides which car `/search-cars`, `/build-dashboard`, and `/car-pulse` use by default.
- `/use-car {name}` switches the active profile; naming a car in any command's arguments overrides it for that run.

When creating a second profile, leave the active profile pointing at whichever car the user says they are currently focused on (ask if unclear).

## Updating an existing profile

If a profile already exists for the requested car:

1. Load it from `${CLAUDE_PLUGIN_DATA}/profiles/`.
2. Show the user what is currently configured.
3. Ask which sections to update, merge the changes, write back to the same path.
4. Re-run the validation step - an edit is as capable of breaking the schema as a fresh write.

## Validation checklist (before writing)

- At least one variant; tiers are integers starting at 0.
- At least one generation with new_prices covering every variant name.
- spec_options keys are unique, lowercase, valid identifiers prefixed `has_` or `is_`.
- search_filters.postcode is not empty.
- At least one search URL source is configured.
