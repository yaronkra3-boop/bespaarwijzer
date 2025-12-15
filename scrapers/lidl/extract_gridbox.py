"""
Lidl Folder Extractor - GridBox Data Method

Extracts food product offers from Lidl's weekly offers page by parsing
the data-gridbox-impression attributes which contain complete product data.

This is a SINGLE SOURCE approach - all data comes from the offers page itself,
no need to visit individual product pages.

Source: https://www.lidl.nl/c/aanbiedingen/a10008785

Data extracted per product:
- name, id
- price (current)
- category (from Lidl's own categorization)
- image URL (high-res)
- product URL

Usage:
  python3 extract_gridbox.py              # Full extraction
  python3 extract_gridbox.py --test       # Test with preview only
"""

import json
import re
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/lidl/folder_data.json"
OFFERS_URL = "https://www.lidl.nl/c/aanbiedingen/a10008785"
SCHWARZ_API_URL = "https://endpoints.leaflets.schwarz/v4/flyer"


def get_folder_info_from_schwarz():
    """Fetch folder metadata (dates) from Schwarz Leaflets API."""
    # Get current week number
    now = datetime.now()
    week_num = now.isocalendar()[1]
    year = now.year

    # Try current week first, then next week
    for week_offset in [0, 1]:
        flyer_id = f"hah-wk{week_num + week_offset}-{year}"
        url = f"{SCHWARZ_API_URL}?flyer_identifier={flyer_id}&region_id=0"

        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            })
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode('utf-8'))

            if data.get('success') and data.get('flyer'):
                flyer = data['flyer']
                return {
                    'name': flyer.get('name', ''),
                    'title': flyer.get('title', ''),
                    'start_date': flyer.get('startDate') or flyer.get('offerStartDate', ''),
                    'end_date': flyer.get('endDate') or flyer.get('offerEndDate', ''),
                    'pdf_url': flyer.get('pdfUrl', ''),
                    'flyer_url': flyer.get('flyerUrlAbsolute', ''),
                }
        except Exception as e:
            print(f"  Warning: Could not fetch folder info for {flyer_id}: {e}")
            continue

    return None

# Category mapping from Lidl's wonCategoryPrimary to our standard categories
# wonCategoryPrimary contains paths like "Werelden van nood/Eten en dichtbij voedsel/Groenten & fruit"
LIDL_WON_CATEGORY_MAP = {
    'groenten & fruit': 'Groente & Fruit',
    'groenten': 'Groente & Fruit',
    'fruit': 'Groente & Fruit',
    'zuivel': 'Zuivel & Eieren',
    'kaas': 'Zuivel & Eieren',
    'eieren': 'Zuivel & Eieren',
    'melk': 'Zuivel & Eieren',
    'worst & vlees': 'Vlees & Vis',
    'vlees': 'Vlees & Vis',
    'vis': 'Vlees & Vis',
    'vleeswaren': 'Vlees & Vis',
    'brood': 'Brood & Gebak',
    'bakkerij': 'Brood & Gebak',
    'gebak': 'Brood & Gebak',
    'dranken': 'Dranken',
    'bier': 'Dranken',
    'wijn': 'Dranken',
    'koffie': 'Dranken',
    'thee': 'Dranken',
    'frisdrank': 'Dranken',
    'sap': 'Dranken',
    'snoep': 'Snacks & Zoetwaren',
    'chips': 'Snacks & Zoetwaren',
    'chocolade': 'Snacks & Zoetwaren',
    'koek': 'Snacks & Zoetwaren',
    'noten': 'Snacks & Zoetwaren',
    'diepvries': 'Diepvries',
    'ijs': 'Diepvries',
    'conserven': 'Houdbaar',
    'pasta': 'Houdbaar',
    'rijst': 'Houdbaar',
    'sauzen': 'Houdbaar',
    'kruiden': 'Houdbaar',
    'ontbijt': 'Houdbaar',
}

# Keywords for more precise categorization
CATEGORY_KEYWORDS = {
    'Groente & Fruit': ['paprika', 'sinaasappel', 'meloen', 'avocado', 'lychee', 'peer', 'aardappel', 'groente', 'fruit', 'sla', 'tomaat', 'komkommer', 'mandarijn', 'appel', 'banaan'],
    'Zuivel & Eieren': ['kaas', 'melk', 'yoghurt', 'boter', 'room', 'eieren', 'zuivel', 'kwark', 'vla'],
    'Vlees & Vis': ['vlees', 'vis', 'kip', 'varken', 'rund', 'zalm', 'garnaal', 'ham', 'bacon', 'worst', 'gehakt', 'filet', 'schnitzel'],
    'Brood & Gebak': ['brood', 'broodje', 'croissant', 'stol', 'kaiser', 'donut', 'taart', 'gebak', 'koek'],
    'Dranken': ['bier', 'wijn', 'glühwein', 'sap', 'water', 'koffie', 'nescaf', 'thee', 'cola', 'coca', 'fanta', 'sprite', 'heineken', 'schweppes', 'prosecco', 'martini'],
    'Snacks & Zoetwaren': ['chips', 'snoep', 'chocola', 'koek', 'noten', 'cashew', 'lay\'s', 'croky', 'm&m', 'maltesers'],
    'Diepvries': ['diepvries', 'ijs', 'pizza', 'viennetta', 'hertog'],
    'Houdbaar': ['pasta', 'rijst', 'saus', 'mayonaise', 'ketchup', 'conserv', 'olie', 'pindakaas', 'jam', 'spread', 'crackers'],
}

# Non-food keywords to filter out
NON_FOOD_KEYWORDS = [
    'silvercrest', 'livarno', 'parkside', 'crivit', 'esmara', 'livergy',
    'meister', 'powerfix', 'florabest', 'ernesto', 'auriol', 'nevadent',
    'badkamer', 'keuken', 'tuin', 'gereedschap', 'kleding', 'schoenen',
    'speelgoed', 'sport', 'auto', 'fiets', 'camping', 'elektronica',
    'computer', 'telefoon', 'lamp', 'meubel', 'textiel', 'handdoek',
    'gordijn', 'kussen', 'dekbed', 'matras', 'stofzuiger', 'mixer',
    'spiegelkast', 'badkamerkast', 'douchegordijn', 'badmat', 'gourmetstel',
    'bloembollen', 'hyacint', 'medinilla', 'phalaenopsis', 'amaryllis',
    'orchidee', 'kerstcactus', 'kamerplant', 'peperomia', 'ilex',
    'kerstster', 'kerstarrangement', 'takken', 'bloem', 'plant',
]

# Known brands for extraction
KNOWN_BRANDS = [
    'nescafé', 'nescafe', 'coca-cola', 'coca cola', 'heineken', 'affligem',
    'calvé', 'calve', 'campina', 'danone', 'activia', 'yakult', 'alpro',
    'lipton', 'unox', 'knorr', 'maggi', 'kellogg', 'quaker', 'douwe egberts',
    'hertog', 'brand', 'grolsch', 'amstel', 'jupiler', 'bavaria',
    'lay\'s', 'lays', 'pringles', 'doritos', 'croky',
    'milka', 'lindt', 'ferrero', 'kinder', 'bounty', 'snickers', 'mars',
    'hero', 'appelsientje', 'optimel', 'danerolles', 'de ruijter',
    'schweppes', 'martini', 'prosecco', 'teisseire', 'lonka',
    'm&m', 'maltesers', 'after eight', 'choclait',
]


def is_food_product(name, category=''):
    """Check if product is food (not home goods, plants, etc)."""
    text = (name + ' ' + category).lower()

    for keyword in NON_FOOD_KEYWORDS:
        if keyword in text:
            return False

    return True


def categorize_product(name, won_category=''):
    """Categorize product based on name and Lidl's wonCategoryPrimary."""
    name_lower = name.lower()
    won_cat_lower = won_category.lower() if won_category else ''

    # First try to match Lidl's wonCategoryPrimary (most accurate)
    # wonCategoryPrimary is like "Werelden van nood/Eten en dichtbij voedsel/Groenten & fruit"
    for key, our_cat in LIDL_WON_CATEGORY_MAP.items():
        if key in won_cat_lower:
            return our_cat

    # Then try keyword matching on name
    for our_category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in name_lower:
                return our_category

    return 'Overig'


def extract_brand(name):
    """Extract brand from product name."""
    name_lower = name.lower()
    for brand in KNOWN_BRANDS:
        if brand in name_lower:
            return brand.title()
    return ''


def main(test_mode=False):
    print("=" * 60)
    print("Lidl Folder Extractor (GridBox Data Method)")
    print("=" * 60)

    # Step 1: Get folder dates from Schwarz API
    print("\nStep 1: Fetching folder dates from Schwarz API...")
    folder_info = get_folder_info_from_schwarz()
    if folder_info:
        print(f"  Folder: {folder_info.get('name', '')} - {folder_info.get('title', '')}")
        print(f"  Valid: {folder_info.get('start_date', '')} to {folder_info.get('end_date', '')}")
    else:
        print("  Warning: Could not fetch folder dates")
        folder_info = {}

    products = []

    # Step 2: Scrape products from Lidl.nl
    print("\nStep 2: Scraping products from Lidl.nl...")
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        print(f"Navigating to {OFFERS_URL}...")
        page.goto(OFFERS_URL, wait_until='networkidle', timeout=60000)

        # Handle cookie consent
        try:
            page.click('button:has-text("Accepteren")', timeout=5000)
            print("  Accepted cookies")
            time.sleep(2)
        except:
            pass

        # Scroll to load all products
        print("  Scrolling to load all products...")
        for i in range(12):
            page.evaluate("window.scrollBy(0, 1500)")
            time.sleep(0.5)

        time.sleep(2)

        # Extract gridbox impression data
        print("\nExtracting product data from gridbox impressions...")

        raw_products = page.evaluate('''() => {
            const products = [];
            const seen = new Set();

            // Find all elements with data-gridbox-impression
            document.querySelectorAll('[data-gridbox-impression]').forEach(el => {
                try {
                    const data = JSON.parse(decodeURIComponent(el.getAttribute('data-gridbox-impression')));

                    // Skip duplicates
                    if (seen.has(data.id)) return;
                    seen.add(data.id);

                    // Get the link href
                    const link = el.querySelector('a[href*="/p/"]') || el.closest('a[href*="/p/"]');
                    const href = link ? link.getAttribute('href') : null;

                    // Get the image
                    const img = el.querySelector('img');
                    const image = img ? (img.src || img.getAttribute('data-src')) : null;

                    // Extract discount data from DOM elements
                    let originalPrice = null;
                    let discountPercent = null;
                    let discountText = '';
                    let unitSize = '';
                    let isLidlPlus = false;

                    // Original price from strikethrough element
                    const strokePriceEl = el.querySelector('.ods-price__stroke-price, s');
                    if (strokePriceEl) {
                        const priceText = strokePriceEl.textContent.trim();
                        const priceMatch = priceText.match(/([0-9]+[.,][0-9]+)/);
                        if (priceMatch) {
                            originalPrice = parseFloat(priceMatch[1].replace(',', '.'));
                        }
                    }

                    // Discount percentage from box content
                    const discountEl = el.querySelector('.ods-price__box-content');
                    if (discountEl) {
                        const discountMatch = discountEl.textContent.match(/-?([0-9]+)%/);
                        if (discountMatch) {
                            discountPercent = parseInt(discountMatch[1]);
                            discountText = discountEl.textContent.trim();
                        }
                    }

                    // Unit size from footer
                    const footerEl = el.querySelector('.ods-price__footer');
                    if (footerEl) {
                        unitSize = footerEl.textContent.trim();
                    }

                    // Check if it's a Lidl Plus offer
                    const lidlPlusEl = el.querySelector('.ods-price__lidl-plus-hint, .ods-price--lidl-plus');
                    if (lidlPlusEl) {
                        isLidlPlus = true;
                        if (!discountText) {
                            discountText = 'Lidl Plus';
                        } else {
                            discountText = 'Lidl Plus ' + discountText;
                        }
                    }

                    products.push({
                        id: data.id,
                        name: data.name,
                        price: data.price,
                        originalPrice: originalPrice,
                        discountPercent: discountPercent,
                        discountText: discountText,
                        unitSize: unitSize,
                        isLidlPlus: isLidlPlus,
                        category: data.category || data.categoryPrimary || '',
                        wonCategory: data.wonCategoryPrimary || '',
                        href: href,
                        image: image,
                        position: data.position,
                        sponsored: data.sponsored || false,
                        listName: data.listName,
                        raw_data: data
                    });
                } catch (e) {
                    // Skip invalid data
                }
            });

            return products;
        }''')

        print(f"  Found {len(raw_products)} products with gridbox data")

        # Filter and enrich products
        print("\nProcessing products...")

        for raw in raw_products:
            # Filter non-food
            if not is_food_product(raw['name'], raw.get('category', '')):
                continue

            # Build discount text for display
            discount_display = raw.get('discountText', '')
            if not discount_display and raw.get('discountPercent'):
                discount_display = f"-{raw['discountPercent']}%"

            product = {
                'id': f"lidl-{raw['id']}",
                'name': raw['name'],
                'price': raw['price'],
                'original_price': raw.get('originalPrice'),
                'discount_percent': raw.get('discountPercent'),
                'discount_text': discount_display,
                'unit_size': raw.get('unitSize', ''),
                'is_lidl_plus': raw.get('isLidlPlus', False),
                'brand': extract_brand(raw['name']),
                'category': categorize_product(raw['name'], raw.get('wonCategory', '')),
                'lidl_category': raw.get('wonCategory', ''),  # Keep Lidl's original category for debugging
                'image_url': raw.get('image', ''),
                'product_url': f"https://www.lidl.nl{raw['href']}" if raw.get('href') else '',
                'sku': raw['id'],
                'currency': '€',
                'source': 'lidl.nl',
                'extraction_method': 'gridbox',
            }

            products.append(product)

        browser.close()

    # Build output
    now = datetime.now()
    folder_week = f"week-{now.isocalendar()[1]}-{now.year}"

    output = {
        'supermarket': 'Lidl',
        'folder_week': folder_week,
        'folder_info': {
            'name': folder_info.get('name', ''),
            'title': folder_info.get('title', ''),
            'start_date': folder_info.get('start_date', ''),
            'end_date': folder_info.get('end_date', ''),
            'pdf_url': folder_info.get('pdf_url', ''),
        },
        'extracted_at': now.isoformat(),
        'source_url': OFFERS_URL,
        'extraction_method': 'gridbox',
        'product_count': len(products),
        'products': products,
    }

    if test_mode:
        print("\n--- TEST MODE: Preview only ---")
    else:
        # Save
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        # Archive
        week_num = now.isocalendar()[1]
        archive_dir = os.path.dirname(OUTPUT_FILE) + '/archive'
        os.makedirs(archive_dir, exist_ok=True)
        archive_file = f"{archive_dir}/folder_data_week_{week_num}_lidl_gridbox.json"
        with open(archive_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'=' * 60}")
    print("Extraction complete!")
    print(f"{'=' * 60}")
    print(f"Total food products: {len(products)}")
    print(f"With prices: {sum(1 for p in products if p.get('price'))}")
    print(f"With original prices: {sum(1 for p in products if p.get('original_price'))}")
    print(f"With discounts: {sum(1 for p in products if p.get('discount_percent'))}")
    print(f"Lidl Plus offers: {sum(1 for p in products if p.get('is_lidl_plus'))}")
    print(f"With brands: {sum(1 for p in products if p.get('brand'))}")
    print(f"With images: {sum(1 for p in products if p.get('image_url'))}")

    if not test_mode:
        print(f"Output saved to: {OUTPUT_FILE}")

    # Show by category
    categories = {}
    for p in products:
        cat = p.get('category', 'Overig')
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n--- Products by Category ---")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Show sample products with discount info
    print(f"\n--- Sample Products ---")
    for p in products[:8]:
        price = f"€{p['price']:.2f}" if p.get('price') else "N/A"
        orig = f"€{p['original_price']:.2f}" if p.get('original_price') else "-"
        discount = p.get('discount_text', '') or '-'
        print(f"  {p['name'][:35]:35} | {orig:>6} → {price:>6} | {discount}")

    return output


if __name__ == "__main__":
    import sys
    test_mode = '--test' in sys.argv
    main(test_mode=test_mode)
