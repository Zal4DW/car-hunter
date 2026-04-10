# Config-Driven Profiles

Car-hunter is built around a single principle: **the car profile JSON is the only source of truth for car-specific data**. Skills, commands, and the Python builder all read from the same profile.

## What belongs in the profile

- Make, model, fuel type, display name
- Variants (name, tier, AutoTrader model string, colour, standard specs)
- Generations (year ranges, detection rules, new prices per variant)
- Spec options (key, label, search terms, regression weight, highlight flag)
- Search URLs (AutoTrader base + params, additional sites, dealer groups)
- Search filter defaults (max price, max mileage, min year, postcode, max distance)
- Registration date mapping (UK reg code -> decimal year)
- Dashboard config (title, theme colours, mileage/budget filter options and defaults)
- Listing ID date encoding flag

## What does NOT belong in skills or the builder

Never hardcode in `SKILL.md` files or `scripts/build_dashboard.py`:
- Variant names, tier numbers, or chart colours
- New prices (RRP)
- Specific spec options or their weights
- Make-specific URLs or search parameters
- Theme colours or dashboard titles

If you catch yourself writing `if variant == "RS e-tron GT"` in a skill, stop. Move it to the profile and read it back via `profile.variants[].name`.

## Why

- Adding a new car (BMW M4, Porsche Taycan, Tesla Model 3) requires only a new profile JSON, not code changes
- Users can fork profiles to tweak weights or filters without touching the plugin
- The schema is documented in `docs/car-profile-schema.md` - keep it current when extending the profile shape

## Referencing profile fields in skills

Use dotted paths consistently so the intent is obvious:
- `profile.search_filters.max_price`
- `profile.variants[].autotrader_model`
- `profile.generations[matching_gen].new_prices[variant_name]`
- `profile.dashboard.theme.bg`

This makes skills readable as templates rather than implementations.
