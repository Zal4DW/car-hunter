# Changelog

## v2.1.0 - 2026-06-09

The biggest release yet: Car Hunter grows from a search-and-dashboard tool into a full used-car buying assistant - reliable enough to trust daily, and with you all the way to the handshake.

### New

- **`/compare-cars`** - answers the cross-shopper's real question: *"what can I get for £40k?"* Compares every car you track (or just the ones you name) at your budget: listings in reach, the newest year and lowest mileage your money buys, typical examples, value retention, and the best-value pick per car - each judged against its own market.
- **`/help-me-negotiate`** - a data-backed negotiation coach. Builds an evidence pack for the exact car you want (price vs the market model, days on forecourt, price-cut history, cheaper comparables, supply pressure), then gives you an opening offer, target, walk-away number, a drafted offer message, and counters to standard dealer tactics.
- **`/car-pulse`** - "anything new? anything cheaper?" answered in seconds from your saved search history, no browser, no rebuild.
- **`/use-car`** - track any number of cars side by side; switch the default profile or just name the car in any command.
- **Quick setup** - `/setup-car` now asks four questions and researches the rest (variants, generations, list prices) for you to confirm. Bundled example profiles ship in `docs/examples/`.
- **Watchlist that survives** - stars persist in your browser across dashboard rebuilds, with a one-click sync command to save them permanently.

### Reliability

- **Deterministic ingest pipeline** - the search step now captures raw listing data and a Python script (`ingest_listings.py`) computes everything derived: listing ids, ages, depreciation, generation detection, and cross-source deduplication. No more hand-computed CSVs.
- **Tolerant dashboard builds** - one bad listing no longer costs you the day's data; bad rows are skipped with a visible warning on the dashboard itself.
- **Date-anchored snapshots** - rebuilding a dashboard the day after a search still diffs the right snapshots and finds the capture record.
- **Profile validation at setup time** - schema mistakes surface immediately (`--validate-profile`), not days later.
- **Hardened HTML output** - scraped strings can no longer break the dashboard's embedded script block.

### Removed

- The legacy composite-key listing-state sidecar (deprecated since 1.x). Snapshot diffing is keyed purely on stable listing ids.

### Internal

- New `tests/repo/` CI gates: manifest version sync, skill/command frontmatter linting, skill length budget, example-profile validation.
- 302 tests, 96% coverage. Machine-readable build summaries (`--summary-json`) for the skill layer.

## v1.3.6 and earlier

Pre-changelog releases: stable listing ids, snapshot diffing, watchlist and capture manifest (#3); template-based HTML rendering and builder hardening (#4).
