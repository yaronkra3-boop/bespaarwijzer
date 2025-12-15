# Architecture Overview

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SCRAPERS                                     │
├─────────────────────────────────────────────────────────────────────┤
│  AH        Dirk       Hoogvliet     Jumbo       Lidl                │
│  (API)    (scrape)    (scrape)      (API)       (API)               │
│    ↓          ↓           ↓           ↓          ↓                   │
│  folder_   folder_    folder_     folder_    folder_                │
│  data.json data.json  data.json   data.json  data.json              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        AGGREGATOR                                    │
│                      (aggregate.py)                                  │
├─────────────────────────────────────────────────────────────────────┤
│  • Normalizes fields across supermarkets                            │
│  • Handles grouped offers (multiple variants = one offer)           │
│  • Extracts folder validity dates                                   │
│  • Calculates discount percentages                                  │
│                              ↓                                       │
│                    aggregated_data.json                             │
│                    (~1900 products)                                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       TRANSFORMER                                    │
│                      (transform.py)                                  │
├─────────────────────────────────────────────────────────────────────┤
│  • Groups products by offer_group_id                                │
│  • Creates grouped offers with variants array                       │
│  • Extracts validity dates per store                                │
│  • Outputs app-ready JSON                                           │
│                              ↓                                       │
│              products.json + folder-validity.json                   │
│                    (~600 grouped offers)                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                           APP                                        │
│                       (index.html)                                   │
├─────────────────────────────────────────────────────────────────────┤
│  • Loads products.json via fetch()                                  │
│  • Client-side search and filtering                                 │
│  • Shopping list with localStorage                                  │
│  • Favorites system                                                 │
│  • Mobile-optimized UI                                              │
└─────────────────────────────────────────────────────────────────────┘
```

## File Purposes

### Scrapers (scrapers/)

Each supermarket has its own extractor:

| File | Purpose |
|------|---------|
| `ah/extract.py` | Albert Heijn API client |
| `dirk/extract.py` | Dirk web scraper |
| `hoogvliet/extract.py` | Hoogvliet web scraper (grouped offers) |
| `jumbo/extract.py` | Jumbo API client |
| `lidl/extract.py` | Lidl API client |

Output: `folder_data.json` in each folder

### Pipeline (pipeline/)

| File | Purpose |
|------|---------|
| `aggregate.py` | Combines all scrapers, normalizes data |
| `transform.py` | Creates app-ready JSON |
| `price_tracker.py` | Historical price database (SQLite) |

### App (app/)

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `index.html` | Application code | Rarely |
| `products.json` | Product data | Weekly |
| `folder-validity.json` | Offer dates | Weekly |

## Key Concepts

### Grouped Offers

Some supermarket offers contain multiple products (e.g., "All M&M varieties").

```javascript
// Grouped offer structure
{
  "id": "hoogvliet_group_123",
  "name": "M&M's",
  "is_grouped_offer": true,
  "variant_count": 6,
  "variants": [
    { "id": "123_1", "name": "M&M's Peanut", "image_url": "..." },
    { "id": "123_2", "name": "M&M's Crispy", "image_url": "..." },
    // ...
  ]
}
```

### Offer Groups

Products linked by `offer_group_id` share the same promotion:
- Same price
- Same discount
- Different variants

### Price Calculation

Multi-buy offers are calculated:
- "2 voor 3.99" → €1.99 each
- "1+1 gratis" → 50% off
- "2e halve prijs" → 25% off

## Historical Price Tracking

The `price_tracker.py` maintains SQLite database:

```python
from price_tracker import PriceTracker

tracker = PriceTracker()
tracker.import_from_aggregated()  # Import current week
history = tracker.get_price_history("melk")
lowest = tracker.get_lowest_price("kaas")
deals = tracker.find_good_deals(threshold_percent=10)
```
