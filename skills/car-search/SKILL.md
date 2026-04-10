---
name: car-search
description: >
  This skill should be used when the user asks to "search for cars",
  "find me a [car name]", "what [car name]s are for sale", "search AutoTrader",
  "update my car search", "run the car search", "look for cars", or any
  request related to searching for used cars currently listed for sale in the UK.
  Config-driven: reads a car profile to determine what to search for.
version: 1.0.0
context: fork
allowed-tools:
  - Read
  - Write
  - Glob
  - Bash
  - WebSearch
  - WebFetch
  - mcp__Claude_in_Chrome__*
---

# Car Search

Search UK car listing websites for used cars matching an active car profile. Compile results into a detailed, cited markdown table with key specifications and distance from the user's home postcode.

## Prerequisites

This skill requires an active car profile in `${CLAUDE_PLUGIN_DATA}/profiles/`. Profiles are user-created and live in the plugin's persistent data directory, not in the plugin install. If no profile exists, direct the user to the `setup-car-profile` skill first.

## Loading the Profile

1. Check `${CLAUDE_PLUGIN_DATA}/profiles/` for available `.json` profile files. If the directory does not exist yet, no profiles have been created - run `setup-car-profile` first.
2. If multiple profiles exist, ask the user which car they want to search for
3. Load the selected `car-profile.json` and use it to configure the entire search

All subsequent instructions reference profile fields. For example, `profile.search_filters.max_price` means the `max_price` value from the `search_filters` section of the loaded profile.

## Default Filters (from profile)

Unless the user specifies otherwise, apply these filters from the profile:

- **Max price:** `profile.search_filters.max_price`
- **Max mileage:** `profile.search_filters.max_mileage`
- **Min year:** `profile.search_filters.min_year`
- **Max distance:** `profile.search_filters.max_distance` miles from `profile.search_filters.postcode`
- **Exclude write-offs:** `profile.search_filters.exclude_write_offs`

If the user provides different filter values, use those instead.

## Search Process

### Step 1: Build search URLs from profile

For each variant in `profile.variants`, construct the AutoTrader search URL:

```
{profile.search_urls.autotrader.base}?make={profile.make}&model={variant.autotrader_model}&{profile.search_urls.autotrader.params}&postcode={profile.search_filters.postcode}&price-to={profile.search_filters.max_price}&maximum-mileage={profile.search_filters.max_mileage}&distance={profile.search_filters.max_distance}&year-from={profile.search_filters.min_year}
```

Also construct URLs for each entry in `profile.search_urls.additional_sites` and `profile.search_urls.dealer_groups`, applying the user's filter parameters where the URL supports them.

### Step 2: Browser-based search (preferred)

Use Claude in Chrome browser tools to navigate directly to each constructed URL. WebFetch is blocked for most car listing sites, so the browser is the primary method.

Search each variant separately on AutoTrader (many cars list variants as different models).

Then check each additional site and dealer group from the profile.

### Step 3: WebSearch fallback

If the browser is unavailable, use WebSearch as a fallback:

- Search `site:autotrader.co.uk {profile.make} {variant.name} for sale`
- Search each additional site: `site:{domain} {profile.make} {model}`
- Search `{profile.display_name} for sale UK {current_year}` for broader results

### Step 4: Individual listing details

For promising listings, navigate to the individual listing page in the browser to extract full details. On AutoTrader, click "View all spec and features" (it is a `<button>` element, not a link) to see the full equipment list.

Use the `profile.spec_options[].search_terms` to identify which optional features each listing has. Match terms case-insensitively against the listing description and spec list.

### Step 5: Deduplication

Many cars appear on multiple platforms. Deduplicate by matching on price + year + mileage + dealer location. When a duplicate is found, link to both sources but count it as one listing.

## Data Points to Extract

For each listing, capture:

- **Price** (asking price in GBP)
- **Model variant** (match against `profile.variants[].name`)
- **Generation** (match against `profile.generations[]` using detection rules)
- **Year** of registration
- **Mileage** in miles
- **Colour**
- **Location** (dealer town/city)
- **Distance from postcode** (estimate based on dealer location vs `profile.search_filters.postcode`)
- **Each spec option** from `profile.spec_options[]`: Yes / No / Not stated
- **Source** (which platform, with direct link to the listing)

For spec options where a variant has the spec as standard (listed in `variant.standard_specs`), mark as "Yes (standard)" rather than checking the listing text.

## Distance Estimation

The user's home postcode is `profile.search_filters.postcode` (`profile.search_filters.location_description`). When searching on AutoTrader with the postcode parameter, distances are shown in the results. For other platforms, estimate driving distance using general UK geography knowledge. Present as approximate miles, e.g. "~45 miles".

## Output File

After compiling results, save the full report as a markdown file.

**Path:** Save to a `{profile.profile_name}-searches/` folder within the user's workspace. Use the naming pattern `{profile.profile_name}-search-{YYYY-MM-DD}.md`. If a file for today's date already exists, overwrite it. Always present the results in the conversation as well as saving the file.

## Output Format

Present results as a markdown table sorted by price (lowest first), grouped by variant. Build the table columns dynamically from the profile:

Fixed columns: `#`, `Price`, `Year`, `Mileage`, `Colour`, `Location (dist.)`, `Days Listed`

Dynamic columns: one column per `profile.spec_options[]` where `highlight` is true (use short labels).

Final column: `Key Options` (remaining non-highlighted specs), `Listing` (clickable links).

```
| # | Price | Year | Mileage | Colour | Location (dist.) | Days Listed | {highlight_spec_1} | {highlight_spec_2} | Key Options | Listing |
```

**IMPORTANT:** The Listing column MUST contain clickable markdown hyperlinks to the actual listing page. Format as `[Platform name](full URL)`. If a car appears on multiple platforms, include all links separated by a comma.

After the table, include:

- **Total listings found** across all sources (after deduplication)
- **Date of search** (today's date)
- **Sources checked** with links and result counts
- **Standout finds** -- highlight the best value, closest to home, lowest mileage, and highest spec options
- Any listings where key details could not be confirmed, flagged clearly

## Listing Tracking and Volatility Analysis

Each search creates a dated snapshot. Over time, these snapshots enable market analysis.

### First Listed Date

If `profile.listing_id_date_encoding.enabled` is true:

For AutoTrader listings, extract the first 8 digits of the listing ID from the URL (e.g. `/car-details/202602179980029` -> `20260217` -> 17 Feb 2026) and record as the **First Listed** date. Calculate **Days on Market** as today's date minus the first listed date.

For Cazoo listings, the search results page shows "Added X days ago" text for some listings. Extract this where available.

For listings on other platforms without date encoding, check previous search reports to determine when the listing was first observed.

### Volatility Metrics

When a previous search report exists in the archive folder, include a **Volatility Analysis** section:

1. **Price Changes** -- identify any car whose asking price changed between searches
2. **Listings Removed** -- cars present previously but absent today (likely sold)
3. **New Listings** -- cars appearing for the first time
4. **Days on Market** -- average, median, and longest-listed car
5. **Summary Statistics:** total today vs previous, price reductions/increases, average change, sold count, new arrivals, net supply change

## CSV Data Collection

After presenting the search results, also compile the data into a CSV file for the dashboard builder. The CSV columns are:

Fixed: `variant`, `generation`, `price`, `year`, `reg`, `reg_date`, `age_years`, `mileage`, `new_price`, `depreciation_total`, `depreciation_pa`, `depreciation_pct`

Dynamic (from profile.spec_options): one boolean column per spec option using the `key` field (e.g. `has_bo`, `has_massage`)

Fixed: `options_count`, `location`, `is_brand_new_stock`

### Calculating derived fields:

- `reg_date`: look up `profile.reg_date_mapping[reg_code]`
- `age_years`: current decimal date minus `reg_date`
- `new_price`: look up `profile.generations[matching_gen].new_prices[variant_name]`
- `depreciation_total`: `new_price - price`
- `depreciation_pa`: `depreciation_total / age_years` (N/A if age < 0.5 years)
- `depreciation_pct`: `(depreciation_total / new_price) * 100`
- `options_count`: count of True spec option columns

Save as: `{profile.profile_name}-searches/{profile.profile_name}-all-listings-{YYYY-MM-DD}.csv`

## Important Notes

- Only include cars genuinely for sale (not sold, reserved, or deposit taken)
- Exclude Cat S/N write-offs unless the user specifically requests them
- For spec options, mark "Not stated" rather than assuming absent if the listing is silent
- Check `variant.standard_specs` before marking a spec as not present -- some specs are standard on certain variants
- Many dealers cross-list on multiple platforms. Always deduplicate.
- Use UK English throughout (organisation, colour, analyse, etc.)

