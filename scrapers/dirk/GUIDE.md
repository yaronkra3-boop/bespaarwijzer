# Dirk Folder Extraction Guide

## Quick Start

```bash
cd /Users/yaronkra/Jarvis/supermarket/dirk
python3 extract.py
python3 generate_html.py
open folder.html
```

---

## Overview

Extract all promotional products from Dirk's weekly folder, including product details and images, and generate an HTML viewer.

**What you get:**
- Product name, brand, packaging
- Offer price and normal price (for discount calculation)
- Product images
- Valid dates (start/end)
- Weekend vs regular deal indicator

---

## How It Works

Dirk's website (`dirk.nl/aanbiedingen`) embeds all offer data in a `__NUXT_DATA__` JSON structure within the HTML. No API calls or authentication needed.

### Key URLs

| Purpose | URL Pattern |
|---------|-------------|
| Offers page | `https://www.dirk.nl/aanbiedingen` |
| Offer images | `https://web-fileserver.dirk.nl/offers/{path}` |
| Catalog images | `https://web-fileserver.dirk.nl/artikelen/{path}` |

**Critical:** Offer images use `/offers/` path. Some products (typically fresh produce) don't have offer images - see `GUIDE-MISSING-IMAGES.md` for how to fetch those from the catalog.

---

## Step 1: Extract Data

Run the extraction script:

```bash
cd /Users/yaronkra/Jarvis/supermarket/dirk
python3 extract.py
```

**Output:** `folder_data.json`

### JSON Structure

```json
{
  "supermarket": "Dirk",
  "folder_week": "week-50-2025",
  "extracted_at": "2025-12-11T17:01:52",
  "source_url": "https://www.dirk.nl/aanbiedingen",
  "product_count": 133,
  "products": [
    {
      "id": 132578,
      "name": "Avocado's ready to eat",
      "brand": "",
      "packaging": "Schaal 2 stuks.",
      "offer_price": 1.49,
      "normal_price": 2.49,
      "discount_text": "ACTIE_",
      "image_url": "https://web-fileserver.dirk.nl/offers/...",
      "start_date": "2025-12-10T00:00:00.000Z",
      "end_date": "2025-12-16T23:59:00.000Z",
      "category": ""
    }
  ]
}
```

### Data Fields

| Field | Description |
|-------|-------------|
| `id` | Dirk's internal offer ID (NOT product catalog ID) |
| `name` | Product name |
| `brand` | Brand name (often empty for store brands) |
| `packaging` | Size/quantity info |
| `offer_price` | Discounted price |
| `normal_price` | Regular price (0 if not provided) |
| `discount_text` | `"ACTIE_"` = regular deal, `"VR, ZA & ZO_actie"` = weekend deal |
| `image_url` | Full URL to product image (empty if missing) |
| `start_date` / `end_date` | Promotion validity period |

---

## Step 2: Check for Missing Images

After extraction, check how many products are missing images:

```bash
grep '"image_url": ""' folder_data.json | wc -l
```

If products are missing images, follow `GUIDE-MISSING-IMAGES.md` to fetch them from Dirk's product catalog.

---

## Step 3: Generate HTML

```bash
python3 generate_html.py
```

Or use inline Python if `generate_html.py` doesn't exist:

```bash
python3 << 'EOF'
import json

with open('folder_data.json', 'r') as f:
    data = json.load(f)

html = '''<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dirk Folder - ''' + (data.get('folder_week') or 'Current') + '''</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f5f5f5; padding: 20px; }
        .header { background: linear-gradient(135deg, #e31837 0%, #c41230 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; text-align: center; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .stats { display: flex; justify-content: center; gap: 40px; margin-top: 20px; }
        .stat-value { font-size: 2em; font-weight: bold; }
        .stat-label { font-size: 0.9em; opacity: 0.8; }
        .filter-bar { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }
        .filter-bar input { flex: 1; min-width: 200px; padding: 10px 15px; border: 1px solid #ddd; border-radius: 6px; }
        .filter-bar select { padding: 10px 15px; border: 1px solid #ddd; border-radius: 6px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }
        .card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .card:hover { transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.15); transition: all 0.2s; }
        .card img { width: 100%; height: 180px; object-fit: contain; background: #fafafa; padding: 10px; }
        .no-img { width: 100%; height: 180px; background: #fafafa; display: flex; align-items: center; justify-content: center; font-size: 3em; color: #ccc; }
        .info { padding: 16px; }
        .name { font-size: 1.1em; font-weight: 600; margin-bottom: 8px; line-height: 1.3; }
        .pack { color: #888; font-size: 0.85em; margin-bottom: 12px; }
        .prices { display: flex; align-items: baseline; gap: 12px; margin-bottom: 8px; }
        .offer { font-size: 1.8em; font-weight: bold; color: #e31837; }
        .normal { font-size: 1em; color: #999; text-decoration: line-through; }
        .save { background: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 600; }
        .badge { background: #e31837; color: white; padding: 4px 10px; border-radius: 4px; font-size: 0.8em; font-weight: bold; display: inline-block; margin-bottom: 8px; }
        .badge.weekend { background: #ff6b00; }
        .dates { font-size: 0.8em; color: #888; border-top: 1px solid #eee; padding-top: 10px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Dirk Folder</h1>
        <div>''' + (data.get('folder_week') or '') + '''</div>
        <div class="stats">
            <div><div class="stat-value">''' + str(len(data['products'])) + '''</div><div class="stat-label">Producten</div></div>
        </div>
    </div>
    <div class="filter-bar">
        <input type="text" id="search" placeholder="Zoek product...">
        <select id="sort">
            <option value="name">Naam</option>
            <option value="price-low">Prijs: laag-hoog</option>
            <option value="price-high">Prijs: hoog-laag</option>
            <option value="discount">Hoogste korting</option>
        </select>
        <span id="count">''' + str(len(data['products'])) + ''' producten</span>
    </div>
    <div class="grid" id="grid"></div>
    <script>
const products = ''' + json.dumps(data['products'], ensure_ascii=False) + ''';

function render(list) {
    const grid = document.getElementById('grid');
    grid.innerHTML = list.map(p => {
        const discount = p.normal_price > 0 ? Math.round((1 - p.offer_price / p.normal_price) * 100) : null;
        const isWeekend = p.discount_text && p.discount_text.includes('ZA');
        const startDate = p.start_date ? new Date(p.start_date).toLocaleDateString('nl-NL', {day:'numeric',month:'short'}) : '';
        const endDate = p.end_date ? new Date(p.end_date).toLocaleDateString('nl-NL', {day:'numeric',month:'short'}) : '';
        return `
        <div class="card">
            ${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" onerror="this.outerHTML='<div class=no-img>📦</div>'">` : '<div class="no-img">📦</div>'}
            <div class="info">
                <div class="badge ${isWeekend ? 'weekend' : ''}">${isWeekend ? 'Weekend' : 'Actie'}</div>
                <div class="name">${p.name}</div>
                ${p.packaging ? `<div class="pack">${p.packaging}</div>` : ''}
                <div class="prices">
                    <span class="offer">€${p.offer_price.toFixed(2)}</span>
                    ${p.normal_price > 0 ? `<span class="normal">€${p.normal_price.toFixed(2)}</span>` : ''}
                    ${discount ? `<span class="save">-${discount}%</span>` : ''}
                </div>
                <div class="dates">${startDate} - ${endDate}</div>
            </div>
        </div>`;
    }).join('');
    document.getElementById('count').textContent = list.length + ' producten';
}

function filterSort() {
    const q = document.getElementById('search').value.toLowerCase();
    const s = document.getElementById('sort').value;
    let list = products.filter(p => p.name.toLowerCase().includes(q) || (p.packaging && p.packaging.toLowerCase().includes(q)));
    if (s === 'price-low') list.sort((a,b) => a.offer_price - b.offer_price);
    else if (s === 'price-high') list.sort((a,b) => b.offer_price - a.offer_price);
    else if (s === 'discount') list.sort((a,b) => {
        const da = a.normal_price > 0 ? (1 - a.offer_price/a.normal_price) : 0;
        const db = b.normal_price > 0 ? (1 - b.offer_price/b.normal_price) : 0;
        return db - da;
    });
    else list.sort((a,b) => a.name.localeCompare(b.name));
    render(list);
}

document.getElementById('search').addEventListener('input', filterSort);
document.getElementById('sort').addEventListener('change', filterSort);
render(products);
    </script>
</body>
</html>'''

with open('folder.html', 'w', encoding='utf-8') as f:
    f.write(html)

with_img = sum(1 for p in data['products'] if p['image_url'])
print(f"Generated folder.html: {with_img}/{len(data['products'])} products with images")
EOF
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
   cd /Users/yaronkra/Jarvis/supermarket/dirk
   python3 extract.py
   ```

2. **Check for missing images:**
   ```bash
   grep '"image_url": ""' folder_data.json
   ```

3. **If missing images exist**, follow `GUIDE-MISSING-IMAGES.md` to fetch them

4. **Generate and view HTML:**
   ```bash
   python3 generate_html.py  # or the inline version above
   open folder.html
   ```

---

## Technical Details

### How the Extractor Works

1. **Fetch page**: GET request to `https://www.dirk.nl/aanbiedingen`
2. **Parse NUXT data**: Extract JSON from `<script id="__NUXT_DATA__">` tag
3. **Dereference indices**: NUXT uses indexed arrays; we resolve references
4. **Build image URLs**: Prepend `https://web-fileserver.dirk.nl/offers/` to image paths
5. **Save JSON**: Write structured data to `folder_data.json`

### Image URL Construction

Raw image path from NUXT: `8/7/5/2/3/1/Avocado's ready to eat_639003678658588847.png`

Full URL: `https://web-fileserver.dirk.nl/offers/8/7/5/2/3/1/Avocado's ready to eat_639003678658588847.png`

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `extract.py` | Main extraction script |
| `generate_html.py` | HTML generator (optional, can use inline) |
| `fetch_missing_images.py` | Automated missing image fetcher |
| `folder_data.json` | Extracted product data |
| `folder.html` | Visual HTML viewer |
| `missing_images.json` | Cache of found catalog images |
| `GUIDE.md` | This guide |
| `GUIDE-MISSING-IMAGES.md` | Guide for missing images |

---

## Troubleshooting

### Images not loading in HTML
- Verify `IMAGE_BASE_URL` in `extract.py` is `https://web-fileserver.dirk.nl/offers/`
- Check browser console for CORS or 404 errors
- Some products genuinely don't have offer images → see missing images guide

### No products extracted
- Dirk may have changed their HTML structure
- Check if `__NUXT_DATA__` script tag still exists on the page
- The NUXT data structure keys may have changed (look for `offerId`, `offerPrice`, etc.)

### Products grid empty in HTML
- Open browser developer console (F12) and check for JavaScript errors
- The `json.dumps()` must be used to properly serialize the products array
- Check for unterminated strings or invalid JSON

---

## Dependencies

- Python 3.x
- `requests` library (for extraction)
- `playwright` (only needed for missing images)

Install if needed:
```bash
pip install requests playwright
playwright install chromium
```

---

*Last updated: December 2025*
