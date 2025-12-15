# Hoogvliet Folder Extraction Guide

## Quick Start

```bash
cd /Users/yaronkra/Jarvis/supermarket/hoogvliet
python3 extract.py
python3 generate_html.py
open folder.html
```

---

## Overview

Extract all promotional products from Hoogvliet's weekly folder, including product details and images, and generate an HTML viewer.

**What you get:**
- Product name and brand
- Offer price (normal price when available)
- Product images
- Category information

---

## How It Works

Hoogvliet uses **Publitas** for their digital folder at `folder.hoogvliet.com`. The folder contains:
1. Page images (PDF-to-image conversion)
2. Hotspots (clickable areas linking to product pages)
3. Each hotspot links to an offer page on hoogvliet.com

### Key URLs

| Purpose | URL Pattern |
|---------|-------------|
| Folder redirect | `https://folder.hoogvliet.com/` |
| Current folder | `https://folder.hoogvliet.com/folder_2025_50/` |
| Folder data | `https://folder.hoogvliet.com/folder_2025_50/data.json` |
| Hotspots data | `https://folder.hoogvliet.com/folder_2025_50/page/2-3/hotspots_data.json` |
| Offer page | `https://www.hoogvliet.com/aanbiedingen/202550181` |
| Offer image | `https://www.hoogvliet.com/INTERSHOP/static/WFS/org-webshop-Site/-/org/nl_NL/ACT/2025/50/230px172px/202550181.jpg` |

---

## Step 1: Extract Data

Run the extraction script:

```bash
cd /Users/yaronkra/Jarvis/supermarket/hoogvliet
python3 extract.py
```

**What the script does:**
1. Gets current folder slug from redirect (e.g., `folder_2025_50`)
2. Fetches folder data to get number of pages
3. Fetches hotspots from all page spreads
4. Filters for `/aanbiedingen/` URLs (offer links)
5. Scrapes each offer page in parallel for product details
6. Constructs image URLs from offer IDs

**Output:** `folder_data.json`

### JSON Structure

```json
{
  "supermarket": "Hoogvliet",
  "folder_week": "week-50-2025",
  "extracted_at": "2025-12-11T18:30:00",
  "source_url": "https://folder.hoogvliet.com/folder_2025_50/",
  "product_count": 98,
  "products": [
    {
      "id": "202550001",
      "name": "Doos chardonnay",
      "brand": "Stoney creek",
      "offer_price": 3.39,
      "normal_price": 3.39,
      "category": "Bier, wijn, alcoholvrij/Wijn, aperitieven/Witte wijn",
      "image_url": "https://www.hoogvliet.com/INTERSHOP/static/.../202550001.jpg",
      "source_url": "https://www.hoogvliet.com/aanbiedingen/202550001"
    }
  ]
}
```

### Data Fields

| Field | Description |
|-------|-------------|
| `id` | Offer ID (YYYYWWXXX format: year, week, sequence) |
| `name` | Product name |
| `brand` | Brand name |
| `offer_price` | Promotional price |
| `normal_price` | Regular price (when available, may equal offer_price) |
| `category` | Product category path |
| `image_url` | Full URL to offer image |
| `source_url` | Link to offer page on hoogvliet.com |

---

## Step 2: Generate HTML

```bash
python3 generate_html.py
```

Then open the HTML:

```bash
open folder.html
```

---

## Complete Workflow

### Weekly Update Process

1. **Extract new folder data:**
   ```bash
   cd /Users/yaronkra/Jarvis/supermarket/hoogvliet
   python3 extract.py
   ```

2. **Generate and view HTML:**
   ```bash
   python3 generate_html.py
   open folder.html
   ```

---

## Technical Details

### How the Extractor Works

1. **Get folder slug**: Follow redirect from `folder.hoogvliet.com` to get current folder (e.g., `folder_2025_50`)
2. **Fetch folder data**: Get `data.json` to determine number of pages/spreads
3. **Fetch hotspots**: For each page spread, get `hotspots_data.json`
4. **Filter URLs**: Keep only URLs containing `/aanbiedingen/`
5. **Scrape offer pages**: Extract name, brand, price, category from HTML
6. **Build image URLs**: Construct from offer ID pattern

### Folder Slug Pattern

- Format: `folder_YYYY_WW` (year, week number)
- Example: `folder_2025_50` = Week 50 of 2025

### Hotspot Page Patterns

- Page 1: `/page/1/hotspots_data.json`
- Pages 2-3: `/page/2-3/hotspots_data.json`
- Pages 4-5: `/page/4-5/hotspots_data.json`
- etc.

### Image URL Patterns

Hoogvliet has **two types of offer IDs** with different image URL patterns:

**Standard weekly offers** (ID starts with year):
- Offer ID: `202550181` → Year `2025`, Week `50`, Sequence `181`
- Image: `/ACT/2025/50/230px172px/202550181.jpg`

**Special/permanent promotions** (non-standard ID):
- Offer ID: `25992334` (doesn't follow YYYYWW pattern)
- Image: `/ACT/2025/50/230px/25992334_zonderCTA.jpg`
- Note the `_zonderCTA` suffix and different folder (`230px` vs `230px172px`)

The extractor handles both by extracting the actual image URL from the offer page HTML, rather than constructing it from the ID.

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `extract.py` | Main extraction script |
| `generate_html.py` | HTML viewer generator |
| `folder_data.json` | Extracted product data |
| `folder.html` | Visual HTML viewer |
| `GUIDE.md` | This guide |

---

## Troubleshooting

### No products extracted
- Check if `folder.hoogvliet.com` redirects properly
- The folder slug format may have changed
- Hotspot URLs may have changed

### Images not loading
- The extractor now extracts image URLs directly from offer pages
- If images still don't load, Hoogvliet may have changed their HTML structure
- Check for `src="` attributes containing the offer ID in page source

### Missing product data
- Hoogvliet offer pages may have changed HTML structure
- Check for `data-track-click` JSON in page source

---

## Differences from Dirk

| Aspect | Dirk | Hoogvliet |
|--------|------|-----------|
| Data source | NUXT JSON in HTML | Publitas folder hotspots |
| Image source | Embedded in NUXT | Constructed from offer ID |
| Normal price | Available | Often missing or same as offer |
| Extraction method | Single page parse | Multi-page hotspot crawl |

---

## Dependencies

- Python 3.x
- `requests` library

Install if needed:
```bash
pip install requests
```

---

*Last updated: December 2025*
