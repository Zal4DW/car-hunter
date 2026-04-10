---
name: setup-car-profile
description: >
  This skill should be used when the user asks to "set up a car search",
  "create a car profile", "add a new car to track", "configure car hunter",
  "set up car-hunter", "I want to search for a [car name]", or any request
  to configure which car model they want to track on the used market.
version: 1.0.0
---

# Setup Car Profile

Create or update a car profile that configures the entire car-hunter plugin for a specific make and model. The profile drives the search skill, CSV schema, dashboard builder, and all analytical features.

## When to Use

- User wants to start tracking a new car model on the used market
- User wants to update their search preferences (budget, location, spec priorities)
- User wants to add a second car profile to compare
- First-time setup of the car-hunter plugin

## Profile Location

Profiles are stored as JSON files in:
```
${CLAUDE_PLUGIN_ROOT}/profiles/{profile-name}.json
```

The schema is documented in `${CLAUDE_PLUGIN_ROOT}/profiles/car-profile-schema.md`.

## Interactive Setup Process

Walk the user through the following sections. Be conversational but thorough. Use AskUserQuestion where possible to keep it structured.

### Step 1: Car Identity

Gather:
- **Make** (manufacturer): e.g. Audi, Porsche, BMW, Tesla, Mercedes
- **Model family**: e.g. e-tron GT, Taycan, i4, Model 3, EQS
- **Fuel type**: Electric, Petrol, Diesel, Hybrid, PHEV

Generate a `profile_name` slug from make + model (lowercase, hyphenated).

### Step 2: Variants

Most car models have trim levels or performance variants. Gather:
- List of variant names **as they appear on AutoTrader** (this is critical for search URLs)
- Assign a numeric tier (0 = base, ascending for higher performance/price)
- Assign a chart colour for each variant (offer sensible defaults based on tier)
- Note which AutoTrader model string to use in URLs (some cars list variants as separate models, others use a single model with trim filters)
- For each variant, note any spec options that are **standard** (e.g. air suspension standard on RS models)

### Step 3: Generations

If the car has distinct generations or facelifts:
- Name each generation (e.g. 'pre-facelift', 'facelift', 'Mk1', 'Mk2')
- Define year ranges
- Provide detection rules (battery size, reg plate ranges, visual identifiers)
- Record the **new price (RRP)** for each variant in each generation. This is essential for depreciation calculations.

If the car has only one generation, create a single generation entry.

### Step 4: Spec Options

These are the optional features the user cares about tracking. For each:
- **key**: a valid Python column name (lowercase, prefixed with `has_` or `is_`)
- **label**: human-readable display name
- **search_terms**: list of strings to look for in listing descriptions (case-insensitive)
- **weight**: regression weight (default 1, premium trims/packages can be 2+)
- **highlight**: whether this is a "must have" spec the user especially wants (shown in purple on dashboard)

Common spec options to suggest (adapt to the car):
- Premium audio system (B&O, Harman Kardon, Burmester, Bose, etc.)
- Massage seats
- Air/adaptive suspension
- Head-up display
- Panoramic roof
- 360-degree camera
- Premium trim level (Vorsprung, M Sport, GTS, etc.)
- Performance package
- Technology package
- Tow bar
- Rear-axle steering

### Step 5: Search Preferences

Gather:
- **Home postcode**: for distance calculations
- **Location description**: human-readable (e.g. "near Daventry, Northamptonshire")
- **Maximum budget**: default search price cap
- **Maximum mileage**: default search mileage cap
- **Minimum year**: earliest registration year to include
- **Maximum distance**: miles from postcode
- **Exclude write-offs**: Cat S/N (default: yes)

### Step 6: Search URLs

Build the AutoTrader search URLs for each variant. The URL pattern is:
```
https://www.autotrader.co.uk/car-search?make={make}&model={model}&include-delivery-option=on&fuel-type={fuel}&postcode={postcode}&sort=price-asc&price-to={max_price}&maximum-mileage={max_mileage}&distance={max_distance}&year-from={min_year}
```

Also ask about additional sites to check:
- Cazoo, Cinch, CarWow, Motorpoint (suggest these as defaults for UK searches)
- Manufacturer approved used programme (e.g. Audi Approved Used, Porsche Approved)
- Major dealer groups relevant to the make (Arnold Clark, Sytner, JCT600, etc.)

### Step 7: Dashboard Preferences

- Confirm the dark theme defaults or offer customisation
- Set filter options for mileage and budget dropdowns
- Set default filter values

### Step 8: Listing ID Date Encoding

Explain that AutoTrader listing IDs encode the advert creation date in their first 8 digits (YYYYMMDD format). This is used to calculate days on market. Confirm this applies (it does for all UK AutoTrader listings).

### Step 9: Registration Date Mapping

For UK cars, provide the standard reg plate to decimal date mapping. This is consistent across all UK cars and doesn't need user input, but confirm the user is searching in the UK.

For non-UK markets, this section would need a different approach.

## Output

After gathering all information:

1. Write the complete `car-profile.json` to `${CLAUDE_PLUGIN_ROOT}/profiles/{profile-name}.json`
2. Generate a `references/{profile-name}-specs.md` file with human-readable spec identification guidance (adapted from the spec_options and search_terms)
3. Present a summary of the profile to the user for review
4. Offer to run the first search immediately using the new profile

## Validation

Before writing the profile:
- Ensure at least one variant is defined
- Ensure at least one generation with new prices is defined
- Ensure spec_options keys are unique and valid Python identifiers
- Ensure search_filters.postcode is not empty
- Ensure at least one search URL source is configured

## Updating an Existing Profile

If a profile already exists for the requested car:
1. Load the existing profile
2. Show the user what's currently configured
3. Ask which sections they want to update
4. Merge changes and write the updated profile
