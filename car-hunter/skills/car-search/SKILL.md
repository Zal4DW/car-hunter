---
name: car-search
description: >
  This skill should be used when the user asks to "search for cars",
  "find me a [car name]", "what [car name]s are for sale", "search AutoTrader",
  "update my car search", "run the car search", "look for cars",
  "check for new listings", "any new cars today", "refresh the car search",
  or any request related to searching for used cars currently listed for
  sale in the UK. Config-driven: reads a car profile to determine what
  to search for, captures raw listings, and hands all derived maths to a
  bundled Python ingest script.
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

Search UK car listing websites for used cars matching a car profile. Your job is **extraction only**: capture what each listing page says into a raw JSON file, then run the bundled ingest script which computes every derived field (ages, depreciation, listing ids, deduplication) and writes the CSV. Never hand-compute derived fields or hand-format CSV rows.

## Prerequisites

An active car profile in `${CLAUDE_PLUGIN_DATA}/profiles/`. If none exists, direct the user to the `setup-car-profile` skill first.

## Loading the Profile

1. If the user named a car, match it against profiles in `${CLAUDE_PLUGIN_DATA}/profiles/` (by `profile_name`, `display_name`, or `make`).
2. Otherwise use the active profile named in `${CLAUDE_PLUGIN_DATA}/active-profile`.
3. Otherwise, if exactly one profile exists, use it; if several, ask the user.

All subsequent instructions reference profile fields, e.g. `profile.search_filters.max_price`.

## Default Filters (from profile)

Apply `profile.search_filters` (max_price, max_mileage, min_year, max_distance from postcode, exclude_write_offs) unless the user specifies otherwise in their request.

## Search Process

### Step 1: Build search URLs from profile

For each variant in `profile.variants`, construct the AutoTrader search URL from `profile.search_urls.autotrader.base` + `params` + the variant's `autotrader_model` + the active filters. Also construct URLs for each entry in `profile.search_urls.additional_sites` and `dealer_groups`.

### Step 2: Browser-based search (preferred)

Use Claude in Chrome browser tools to navigate to each URL. WebFetch is blocked for most car listing sites, so the browser is the primary method. Search each variant separately on AutoTrader (many cars list variants as different models). Fall back to WebSearch (`site:autotrader.co.uk {make} {variant} for sale`) only if the browser is unavailable.

### Step 3: Paginate exhaustively

For each source, follow `?page=N` (or the site's equivalent) until a page returns zero new listings. On AutoTrader, read the pagination footer ("Page 1 of 4") to know the expected count. Track per source: `name`, `url`, `expected_pages`, `captured_pages`, and `status` (`ok` / `partial` / `failed`). A missed page today looks like a "sold" car tomorrow.

### Step 4: Individual listing details

For each listing, open the page and extract the raw data points below. On AutoTrader, click "View all spec and features" (a `<button>`, not a link) to see the full equipment list. Match `profile.spec_options[].search_terms` case-insensitively against the description and spec list. Check `variant.standard_specs` - those specs are present even when the listing is silent.

## Data to Extract (raw, per listing)

- `url` - the full listing URL (this is what the ingest script derives the stable id from)
- `source` - platform name (AutoTrader, Cinch, dealer name...)
- `variant` - matched against `profile.variants[].name` exactly
- `price` - as shown, raw text is fine ("£42,995")
- `year` - registration year
- `reg` - UK reg plate code if shown (e.g. "74")
- `mileage` - as shown, raw text is fine ("12,400 miles")
- `colour`, `location` - dealer town/city
- `specs` - list of `profile.spec_options[].key` values whose search terms matched
- `is_brand_new_stock` - true for unregistered/delivery-miles stock

Mark spec options "not stated" by simply omitting them; never guess.

## Write the raw capture JSON

Save everything to `{profile.profile_name}-searches/{profile.profile_name}-raw-capture-{YYYY-MM-DD}.json` in the user's workspace (create the folder if needed):

```json
{
  "captured": "YYYY-MM-DD",
  "sources": [
    {"name": "AutoTrader", "url": "...", "expected_pages": 4, "captured_pages": 4, "status": "ok"}
  ],
  "listings": [
    {"url": "...", "source": "AutoTrader", "variant": "...", "price": "£42,995",
     "year": 2024, "reg": "74", "mileage": "12,400 miles", "colour": "Blue",
     "location": "Leeds", "specs": ["has_pano"], "is_brand_new_stock": false}
  ]
}
```

**Write this file even when a source fails completely** - a red capture badge is informative; a missing one is ambiguous. Record every source you attempted with its status.

## Run the ingest script

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ingest_listings.py" \
  --profile "${CLAUDE_PLUGIN_DATA}/profiles/{profile_name}.json" \
  --capture "{profile_name}-searches/{profile_name}-raw-capture-{YYYY-MM-DD}.json"
```

The script computes listing ids, registration dates, ages, depreciation, generation detection, and options counts; collapses cross-source duplicates (preferring the canonical AutoTrader id); and writes the dated CSV plus the capture manifest next to the capture file. Read its output: it names any skipped listings with reasons - re-check those pages or correct the capture JSON and re-run rather than leaving rows behind silently.

## Markdown report

After ingesting, present the results in the conversation AND save a report to `{profile_name}-searches/{profile_name}-search-{YYYY-MM-DD}.md` (overwrite same-day files). Build it from the ingested CSV, sorted by price ascending, grouped by variant:

```
| # | Price | Year | Mileage | Colour | Location (dist.) | Days Listed | {highlight specs...} | Key Options | Listing |
```

- One column per `profile.spec_options[]` where `highlight` is true; remaining specs go in Key Options.
- The Listing column MUST contain clickable markdown links to the actual listing pages.
- Estimate distances from `profile.search_filters.postcode` (AutoTrader shows them directly).

After the table include: total listings after deduplication, sources checked with result counts, standout finds (best value, closest, lowest mileage, highest spec), and any listings with unconfirmed details flagged clearly.

## Important Notes

- Only include cars genuinely for sale (not sold, reserved, or deposit taken).
- Exclude Cat S/N write-offs unless the user requests them.
- Variants must match `profile.variants[].name` exactly - the ingest script warns on unknown variants.
- Deduplication is handled by the ingest script; just capture everything you see, including apparent cross-site duplicates.
- After the search, suggest `/build-dashboard` to refresh the analysis, or `/car-pulse` for a quick what-changed digest.
- Use UK English throughout (organisation, colour, analyse, etc.).
