# Car Profile Schema

This document defines the `car-profile.json` schema used by the car-hunter plugin. Each profile describes a single car model (or family of variants) that the user wants to track on the used market.

## Schema Definition

```json
{
  "profile_name": "string — unique slug, e.g. 'audi-etron-gt'",
  "display_name": "string — human-readable, e.g. 'Audi e-tron GT'",
  "make": "string — manufacturer, e.g. 'Audi'",
  "fuel_type": "string — Electric | Petrol | Diesel | Hybrid | PHEV | Any",

  "variants": [
    {
      "name": "string — exact variant name as it appears on listings, e.g. 'e-tron GT quattro'",
      "tier": "integer — 0 = base, 1 = mid, 2 = top. Used as regression feature.",
      "colour": {
        "border": "string — hex colour for charts, e.g. '#3b82f6'",
        "bg": "string — rgba background, e.g. 'rgba(59,130,246,0.15)'",
        "point": "string — hex point colour, e.g. '#3b82f6'"
      },
      "autotrader_model": "string — model name as it appears in AutoTrader URLs, e.g. 'e-tron%20GT'",
      "standard_specs": ["string — spec keys that are standard on this variant, e.g. 'has_air_susp'"]
    }
  ],

  "generations": [
    {
      "name": "string — e.g. 'pre-facelift'",
      "label": "string — display label, e.g. 'Pre-facelift (93.4kWh)'",
      "year_from": "integer — first registration year",
      "year_to": "integer|null — last registration year (null = current)",
      "detection_rules": {
        "battery_kwh": "number|null — battery size identifier",
        "max_reg": "string|null — latest UK reg plate code, e.g. '74'",
        "min_reg": "string|null — earliest UK reg plate code, e.g. '75'"
      },
      "new_prices": {
        "variant_name": "integer — RRP when new for each variant in this generation"
      }
    }
  ],

  "spec_options": [
    {
      "key": "string — CSV column name, e.g. 'has_bo'",
      "label": "string — display label, e.g. 'B&O Sound'",
      "search_terms": ["string — terms to look for in listing descriptions, e.g. 'B&O', 'Bang & Olufsen'"],
      "weight": "number — regression weight for spec_score calculation. Default 1. Premium trims can be 2+.",
      "highlight": "boolean — whether to highlight this spec in the dashboard (purple tag). Default false."
    }
  ],

  "search_filters": {
    "postcode": "string — user's home postcode for distance calc, e.g. 'NN6 9SH'",
    "location_description": "string — human-readable location, e.g. 'near Daventry, Northamptonshire'",
    "max_price": "integer — default max budget in GBP",
    "max_mileage": "integer — default max mileage in miles",
    "min_year": "integer — earliest registration year to include",
    "max_distance": "integer — max miles from postcode",
    "exclude_write_offs": "boolean — exclude Cat S/N. Default true."
  },

  "search_urls": {
    "autotrader": {
      "base": "https://www.autotrader.co.uk/car-search",
      "params": {
        "make": "string",
        "include-delivery-option": "on",
        "fuel-type": "string",
        "postcode": "string — from search_filters",
        "sort": "price-asc",
        "price-to": "integer — from search_filters.max_price",
        "maximum-mileage": "integer — from search_filters.max_mileage",
        "distance": "integer — from search_filters.max_distance",
        "year-from": "integer — from search_filters.min_year"
      }
    },
    "additional_sites": [
      {
        "name": "string — e.g. 'Cazoo'",
        "urls": ["string — full URLs to check"],
        "notes": "string — any parsing hints"
      }
    ],
    "dealer_groups": [
      {
        "name": "string — e.g. 'Arnold Clark'",
        "url": "string — search URL for this make/model",
        "notes": "string — deduplication warnings etc."
      }
    ]
  },

  "listing_id_date_encoding": {
    "enabled": "boolean — whether the listing site encodes dates in IDs",
    "source": "string — e.g. 'autotrader'",
    "format": "string — e.g. 'YYYYMMDD_first_8_digits'"
  },

  "reg_date_mapping": {
    "description": "UK registration plate to decimal date mapping",
    "entries": {
      "reg_code": "decimal_date — e.g. '71': 2021.75"
    }
  },

  "dashboard": {
    "title": "string — dashboard page title",
    "theme": {
      "bg": "string — page background colour",
      "card_bg": "string — card background",
      "card_border": "string — card border",
      "text": "string — main text colour",
      "text_muted": "string — muted text colour"
    },
    "mileage_filter_options": [10000, 20000, 30000, 50000, 100000],
    "mileage_filter_default": 20000,
    "budget_filter_options": [40000, 50000, 60000, 80000, 100000],
    "budget_filter_default": 50000
  },

  "metadata": {
    "created": "string — ISO date",
    "updated": "string — ISO date",
    "version": "string — schema version, e.g. '1.0.0'"
  }
}
```

## Notes

- The `variants` array order matters: tier 0 first, ascending. The tier value is used directly as a numeric feature in the regression model.
- `spec_options` defines both the CSV columns and the dashboard rendering. The `key` must be a valid Python/CSV column name (lowercase, underscore-separated, prefixed with `has_` or `is_`).
- `search_terms` in spec_options are used by the search skill to identify features from listing text. Case-insensitive matching.
- `highlight` specs are shown in purple in the dashboard and represent the user's preferred/target specifications.
- `generations` support multiple concurrent generations. The `detection_rules` allow the dashboard to classify listings automatically.
- `reg_date_mapping` is UK-specific. For other markets, this could be replaced with a different date estimation method.
- The `search_urls` section is designed to be extensible. AutoTrader is the primary UK source, but additional sites and dealer groups can be added per profile.

