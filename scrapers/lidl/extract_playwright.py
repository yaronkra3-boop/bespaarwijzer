"""
Lidl Folder Extractor - Playwright Version

Extracts food product offers from Lidl's weekly offers page using Playwright
to render the JavaScript-heavy page and extract full product data.

Source: https://www.lidl.nl/c/aanbiedingen/a10008785

Strategy:
1. Load the offers page and scroll to get all products
2. Collect all product URLs from the page
3. Visit each product page to get full details from JSON-LD

Data extracted per product:
- name, brand
- price (current and original)
- discount percentage
- category
- image URL (high-res)
- product URL
- SKU

Usage:
  python3 extract_playwright.py              # Full extraction
  python3 extract_playwright.py --test       # Test with first 10 products
"""

import json
import re
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

OUTPUT_FILE = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/lidl/folder_data.json"
OFFERS_URL = "https://www.lidl.nl/c/aanbiedingen/a10008785"

# Category mapping from Dutch to our standard categories
CATEGORY_MAP = {
    'groente': 'Groente & Fruit',
    'fruit': 'Groente & Fruit',
    'aardappel': 'Groente & Fruit',
    'sinaasappel': 'Groente & Fruit',
    'meloen': 'Groente & Fruit',
    'avocado': 'Groente & Fruit',
    'lychee': 'Groente & Fruit',
    'paprika': 'Groente & Fruit',
    'peer': 'Groente & Fruit',
    'zuivel': 'Zuivel & Eieren',
    'kaas': 'Zuivel & Eieren',
    'eieren': 'Zuivel & Eieren',
    'melk': 'Zuivel & Eieren',
    'yoghurt': 'Zuivel & Eieren',
    'boter': 'Zuivel & Eieren',
    'room': 'Zuivel & Eieren',
    'vlees': 'Vlees & Vis',
    'vis': 'Vlees & Vis',
    'kip': 'Vlees & Vis',
    'varken': 'Vlees & Vis',
    'rund': 'Vlees & Vis',
    'zalm': 'Vlees & Vis',
    'garnaal': 'Vlees & Vis',
    'ham': 'Vlees & Vis',
    'bacon': 'Vlees & Vis',
    'worst': 'Vlees & Vis',
    'brood': 'Brood & Gebak',
    'gebak': 'Brood & Gebak',
    'bakkerij': 'Brood & Gebak',
    'croissant': 'Brood & Gebak',
    'stol': 'Brood & Gebak',
    'kaiser': 'Brood & Gebak',
    'drank': 'Dranken',
    'bier': 'Dranken',
    'wijn': 'Dranken',
    'glühwein': 'Dranken',
    'sap': 'Dranken',
    'water': 'Dranken',
    'koffie': 'Dranken',
    'nescaf': 'Dranken',
    'thee': 'Dranken',
    'frisdrank': 'Dranken',
    'cola': 'Dranken',
    'coca': 'Dranken',
    'heineken': 'Dranken',
    'chips': 'Snacks & Zoetwaren',
    'snoep': 'Snacks & Zoetwaren',
    'chocola': 'Snacks & Zoetwaren',
    'koek': 'Snacks & Zoetwaren',
    'noten': 'Snacks & Zoetwaren',
    'cashew': 'Snacks & Zoetwaren',
    'diepvries': 'Diepvries',
    'ijs': 'Diepvries',
    'pizza': 'Diepvries',
    'pasta': 'Houdbaar',
    'rijst': 'Houdbaar',
    'saus': 'Houdbaar',
    'mayonaise': 'Houdbaar',
    'ketchup': 'Houdbaar',
    'conserv': 'Houdbaar',
    'olie': 'Houdbaar',
}

# Known brands to extract from product names
KNOWN_BRANDS = [
    'nescafé', 'nescafe', 'coca-cola', 'coca cola', 'heineken', 'affligem',
    'calvé', 'calve', 'campina', 'danone', 'activia', 'yakult', 'alpro',
    'lipton', 'unox', 'knorr', 'maggi', 'kellogg', 'quaker', 'douwe egberts',
    'jacobs', 'lavazza', 'illy', 'senseo', 'nespresso', 'dolce gusto',
    'hertog jan', 'brand', 'grolsch', 'amstel', 'jupiler', 'bavaria',
    'spa', 'evian', 'perrier', 'san pellegrino', 'fanta', 'sprite', '7up',
    'red bull', 'monster', 'innocent', 'tropicana', 'minute maid',
    'lay\'s', 'lays', 'pringles', 'doritos', 'cheetos', 'bugles',
    'milka', 'lindt', 'ferrero', 'kinder', 'bounty', 'snickers', 'mars',
    'twix', 'kitkat', 'kit kat', 'tony\'s', 'tonys', 'verkade', 'lu',
    'oreo', 'bastogne', 'speculoos', 'stroopwafel',
    'becel', 'blue band', 'bertolli', 'carbonell',
    'hellmann', 'heinz', 'devos lemmens', 'gouda\'s glorie',
    'nutella', 'lotus', 'biscoff',
]

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


def categorize_product(name, url=''):
    """Categorize product based on name and URL keywords."""
    text = (name + ' ' + url).lower()

    for keyword, category in CATEGORY_MAP.items():
        if keyword in text:
            return category

    return 'Overig'


def is_food_product(name, url=''):
    """Check if product is food (not home goods, clothing, etc)."""
    text = (name + ' ' + url).lower()

    for keyword in NON_FOOD_KEYWORDS:
        if keyword in text:
            return False

    return True


def extract_brand_from_name(name):
    """Extract brand from product name using known brands list."""
    name_lower = name.lower()
    for brand in KNOWN_BRANDS:
        if brand in name_lower:
            # Return the brand with proper capitalization
            return brand.title()
    return ''


def collect_product_urls(page):
    """Collect all unique product URLs from the offers page."""
    print("  Scrolling to load all products...")

    # Scroll down multiple times to trigger lazy loading
    for i in range(10):
        page.evaluate("window.scrollBy(0, 1000)")
        time.sleep(0.5)

    # Scroll back to top
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(2)

    # Collect all product links
    print("  Collecting product URLs...")
    seen_urls = set()
    products = []

    all_links = page.query_selector_all('a[href*="/p/"]')

    for link in all_links:
        href = link.get_attribute('href')
        if href and '/p/' in href and href not in seen_urls:
            seen_urls.add(href)
            name = link.get_attribute('title') or link.inner_text().strip()
            if name and len(name) > 1:
                full_url = f"https://www.lidl.nl{href}" if href.startswith('/') else href
                # Extract product ID
                match = re.search(r'/p(\d+)', href)
                product_id = match.group(1) if match else str(hash(href))

                products.append({
                    'id': f"lidl-{product_id}",
                    'name': name,
                    'product_url': full_url,
                })

    return products


def fetch_product_details(page, product):
    """Fetch detailed product info from individual product page using JSON-LD."""
    url = product.get('product_url')
    if not url:
        return product

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=15000)
        time.sleep(0.5)

        # Look for JSON-LD structured data
        json_ld_elements = page.query_selector_all('script[type="application/ld+json"]')

        for json_ld in json_ld_elements:
            try:
                data = json.loads(json_ld.inner_text())
                if data.get('@type') == 'Product':
                    # Extract all the good stuff
                    product['name'] = data.get('name', product.get('name', ''))

                    brand_info = data.get('brand', {})
                    if isinstance(brand_info, dict):
                        product['brand'] = brand_info.get('name', '')
                    else:
                        product['brand'] = str(brand_info) if brand_info else ''

                    product['sku'] = data.get('sku', '')

                    # Get images
                    images = data.get('image', [])
                    if images:
                        product['image_url'] = images[0] if isinstance(images, list) else images

                    # Get price from offers
                    offers = data.get('offers', [])
                    if offers:
                        offer = offers[0] if isinstance(offers, list) else offers
                        product['price'] = offer.get('price')
                        product['currency'] = offer.get('priceCurrency', '€')

                    # Get ratings if available
                    rating = data.get('aggregateRating', {})
                    if rating:
                        product['rating'] = rating.get('ratingValue')
                        product['rating_count'] = rating.get('ratingCount')

                    break
            except json.JSONDecodeError:
                continue

    except Exception as e:
        print(f"    Warning: Error fetching {url}: {str(e)[:50]}")

    return product


def main(test_mode=False):
    print("=" * 60)
    print("Lidl Folder Extractor (Playwright)")
    print("=" * 60)

    all_products = []

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

        # Handle cookie consent if present
        try:
            page.click('button:has-text("Accepteren")', timeout=5000)
            print("  Accepted cookies")
            time.sleep(2)
        except:
            pass

        # Wait for content to load
        time.sleep(5)

        # Step 1: Collect all product URLs from the offers page
        print("\nStep 1: Collecting product URLs from offers page...")
        products = collect_product_urls(page)
        print(f"  Found {len(products)} unique products")

        # Filter to food products only
        food_products = [p for p in products if is_food_product(p.get('name', ''), p.get('product_url', ''))]
        print(f"  Filtered to {len(food_products)} food products")

        # In test mode, only process first 10
        if test_mode:
            food_products = food_products[:10]
            print(f"  Test mode: processing only {len(food_products)} products")

        # Step 2: Visit each product page to get full details
        print(f"\nStep 2: Fetching details for {len(food_products)} products...")
        for i, product in enumerate(food_products):
            print(f"  [{i+1}/{len(food_products)}] {product.get('name', 'Unknown')[:50]}")
            product = fetch_product_details(page, product)

            # Add category
            product['category'] = categorize_product(
                product.get('name', ''),
                product.get('product_url', '')
            )

            # Try to extract brand from name if not already set
            if not product.get('brand'):
                product['brand'] = extract_brand_from_name(product.get('name', ''))

            # Set defaults
            product.setdefault('brand', '')
            product.setdefault('price', None)
            product.setdefault('original_price', None)
            product.setdefault('discount_text', '')
            product.setdefault('image_url', '')
            product.setdefault('currency', '€')
            product['source'] = 'lidl.nl'

            all_products.append(product)

        browser.close()

    # Build output
    now = datetime.now()
    folder_week = f"week-{now.isocalendar()[1]}-{now.year}"

    output = {
        'supermarket': 'Lidl',
        'folder_week': folder_week,
        'extracted_at': now.isoformat(),
        'source_url': OFFERS_URL,
        'extraction_method': 'playwright',
        'product_count': len(all_products),
        'products': all_products,
    }

    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Archive
    week_num = now.isocalendar()[1]
    archive_dir = os.path.dirname(OUTPUT_FILE) + '/archive'
    os.makedirs(archive_dir, exist_ok=True)
    archive_file = f"{archive_dir}/folder_data_week_{week_num}_lidl_playwright.json"
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'=' * 60}")
    print("Extraction complete!")
    print(f"{'=' * 60}")
    print(f"Total food products: {len(all_products)}")
    print(f"With prices: {sum(1 for p in all_products if p.get('price'))}")
    print(f"With brands: {sum(1 for p in all_products if p.get('brand'))}")
    print(f"With images: {sum(1 for p in all_products if p.get('image_url'))}")
    print(f"Output saved to: {OUTPUT_FILE}")

    # Show by category
    categories = {}
    for p in all_products:
        cat = p.get('category', 'Overig')
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n--- Products by Category ---")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Show sample products
    print(f"\n--- Sample Products ---")
    for p in all_products[:5]:
        price = f"€{p['price']:.2f}" if p.get('price') else "N/A"
        brand = p.get('brand', '-') or '-'
        print(f"  {p['name'][:40]:40} | {brand[:15]:15} | {price}")

    return output


if __name__ == "__main__":
    import sys
    test_mode = '--test' in sys.argv
    main(test_mode=test_mode)
