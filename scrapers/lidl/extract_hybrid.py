"""
Lidl Folder Extractor - Hybrid Version

Combines multiple data sources for best coverage:
1. Playwright scraping of lidl.nl/aanbiedingen for product URLs
2. JSON-LD extraction from individual product pages for full details
3. Schwarz API for folder metadata (dates, validity)
4. Fallback to supermarktaanbiedingen.com for products we missed

Focus: FOOD PRODUCTS ONLY - strict filtering of non-food items

Usage:
  python3 extract_hybrid.py              # Full extraction
  python3 extract_hybrid.py --test       # Test with first 10 products
"""

import json
import re
import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/lidl/folder_data.json"
OFFERS_URL = "https://www.lidl.nl/c/aanbiedingen/a10008785"
SCHWARZ_API = "https://endpoints.leaflets.schwarz/v4/flyer"
BACKUP_SOURCE = "https://www.supermarktaanbiedingen.com/aanbiedingen/lidl"

# Category mapping - comprehensive
CATEGORY_MAP = {
    # Groente & Fruit
    'groente': 'Groente & Fruit', 'fruit': 'Groente & Fruit',
    'aardappel': 'Groente & Fruit', 'sinaasappel': 'Groente & Fruit',
    'meloen': 'Groente & Fruit', 'avocado': 'Groente & Fruit',
    'lychee': 'Groente & Fruit', 'paprika': 'Groente & Fruit',
    'peer': 'Groente & Fruit', 'appel': 'Groente & Fruit',
    'banaan': 'Groente & Fruit', 'tomaat': 'Groente & Fruit',
    'komkommer': 'Groente & Fruit', 'sla': 'Groente & Fruit',
    'ui': 'Groente & Fruit', 'wortel': 'Groente & Fruit',
    'champignon': 'Groente & Fruit', 'broccoli': 'Groente & Fruit',

    # Zuivel & Eieren
    'zuivel': 'Zuivel & Eieren', 'kaas': 'Zuivel & Eieren',
    'eieren': 'Zuivel & Eieren', 'melk': 'Zuivel & Eieren',
    'yoghurt': 'Zuivel & Eieren', 'boter': 'Zuivel & Eieren',
    'room': 'Zuivel & Eieren', 'kwark': 'Zuivel & Eieren',
    'vla': 'Zuivel & Eieren', 'campina': 'Zuivel & Eieren',
    'optimel': 'Zuivel & Eieren', 'goudse': 'Zuivel & Eieren',

    # Vlees & Vis
    'vlees': 'Vlees & Vis', 'vis': 'Vlees & Vis',
    'kip': 'Vlees & Vis', 'varken': 'Vlees & Vis',
    'rund': 'Vlees & Vis', 'zalm': 'Vlees & Vis',
    'garnaal': 'Vlees & Vis', 'ham': 'Vlees & Vis',
    'bacon': 'Vlees & Vis', 'worst': 'Vlees & Vis',
    'gehakt': 'Vlees & Vis', 'filet': 'Vlees & Vis',
    'schnitzel': 'Vlees & Vis', 'cordon': 'Vlees & Vis',

    # Brood & Gebak
    'brood': 'Brood & Gebak', 'gebak': 'Brood & Gebak',
    'bakkerij': 'Brood & Gebak', 'croissant': 'Brood & Gebak',
    'stol': 'Brood & Gebak', 'kaiser': 'Brood & Gebak',
    'donut': 'Brood & Gebak', 'afbak': 'Brood & Gebak',
    'stokbrood': 'Brood & Gebak', 'pistolet': 'Brood & Gebak',

    # Dranken
    'drank': 'Dranken', 'bier': 'Dranken', 'wijn': 'Dranken',
    'glühwein': 'Dranken', 'sap': 'Dranken', 'water': 'Dranken',
    'koffie': 'Dranken', 'nescaf': 'Dranken', 'thee': 'Dranken',
    'frisdrank': 'Dranken', 'cola': 'Dranken', 'coca': 'Dranken',
    'heineken': 'Dranken', 'affligem': 'Dranken', 'prosecco': 'Dranken',
    'martini': 'Dranken', 'schweppes': 'Dranken', 'appelsientje': 'Dranken',
    'ijsthee': 'Dranken', 'ice tea': 'Dranken',

    # Snacks & Zoetwaren
    'chips': 'Snacks & Zoetwaren', 'snoep': 'Snacks & Zoetwaren',
    'chocola': 'Snacks & Zoetwaren', 'koek': 'Snacks & Zoetwaren',
    'noten': 'Snacks & Zoetwaren', 'cashew': 'Snacks & Zoetwaren',
    'lay\'s': 'Snacks & Zoetwaren', 'pringles': 'Snacks & Zoetwaren',
    'doritos': 'Snacks & Zoetwaren', 'croky': 'Snacks & Zoetwaren',
    'm&m': 'Snacks & Zoetwaren', 'maltesers': 'Snacks & Zoetwaren',
    'cracker': 'Snacks & Zoetwaren', 'toast': 'Snacks & Zoetwaren',

    # Diepvries
    'diepvries': 'Diepvries', 'ijs': 'Diepvries',
    'pizza': 'Diepvries', 'viennetta': 'Diepvries',
    'hertog': 'Diepvries',

    # Houdbaar
    'pasta': 'Houdbaar', 'rijst': 'Houdbaar', 'saus': 'Houdbaar',
    'mayonaise': 'Houdbaar', 'ketchup': 'Houdbaar',
    'conserv': 'Houdbaar', 'olie': 'Houdbaar',
    'calvé': 'Houdbaar', 'calve': 'Houdbaar',
    'pindakaas': 'Houdbaar', 'jam': 'Houdbaar',
    'spread': 'Houdbaar', 'ruijter': 'Houdbaar',
}

# Known food brands
KNOWN_BRANDS = [
    'nescafé', 'nescafe', 'coca-cola', 'coca cola', 'heineken', 'affligem',
    'calvé', 'calve', 'campina', 'danone', 'activia', 'yakult', 'alpro',
    'lipton', 'unox', 'knorr', 'maggi', 'kellogg', 'quaker', 'douwe egberts',
    'jacobs', 'lavazza', 'illy', 'senseo', 'hertog jan', 'grolsch', 'amstel',
    'spa', 'evian', 'fanta', 'sprite', 'red bull', 'innocent', 'tropicana',
    'lay\'s', 'lays', 'pringles', 'doritos', 'croky', 'milka', 'lindt',
    'ferrero', 'kinder', 'bounty', 'snickers', 'mars', 'twix', 'kitkat',
    'oreo', 'verkade', 'lu', 'becel', 'blue band', 'bertolli',
    'hellmann', 'heinz', 'nutella', 'lotus', 'schweppes', 'appelsientje',
    'hero', 'optimel', 'de ruijter', 'danerolles', 'martini', 'viennetta',
]

# Strict non-food filter - these are DEFINITELY not food
NON_FOOD_KEYWORDS = [
    # Lidl brands for non-food
    'silvercrest', 'livarno', 'parkside', 'crivit', 'esmara', 'livergy',
    'meister', 'powerfix', 'florabest', 'ernesto', 'auriol', 'nevadent',
    'lupilu', 'playtive', 'tronic', 'ultimate speed', 'zoofari', 'miomare',

    # Home & Garden
    'badkamer', 'keuken', 'tuin', 'gereedschap', 'kleding', 'schoenen',
    'speelgoed', 'sport', 'auto', 'fiets', 'camping', 'elektronica',
    'computer', 'telefoon', 'lamp', 'meubel', 'textiel', 'handdoek',
    'gordijn', 'kussen', 'dekbed', 'matras', 'stofzuiger', 'mixer',
    'spiegelkast', 'badkamerkast', 'douchegordijn', 'badmat', 'gourmetstel',

    # Plants & Flowers
    'bloembollen', 'hyacint', 'medinilla', 'phalaenopsis', 'amaryllis',
    'orchidee', 'kerstcactus', 'kamerplant', 'peperomia', 'ilex',
    'kerstster', 'kerstarrangement', 'takken', 'bloem', 'plant', 'pot',

    # Other non-food
    'hoodie', 'trui', 'broek', 'jas', 'shirt', 'sok', 'ondergoed',
    'platenspeler', 'batterij', 'oplader', 'kabel', 'adapter',
    'percolator', 'bialetti', 'hasbro', 'spellen', 'houten',
    'led-lamp', 'osram', 'knuffel',
]


def categorize_product(name, url=''):
    """Categorize product based on name and URL keywords."""
    text = (name + ' ' + url).lower()

    for keyword, category in CATEGORY_MAP.items():
        if keyword in text:
            return category

    return 'Overig'


def is_food_product(name, url=''):
    """Strict check if product is food."""
    text = (name + ' ' + url).lower()

    # First check: if it contains any non-food keyword, reject it
    for keyword in NON_FOOD_KEYWORDS:
        if keyword in text:
            return False

    # Second check: if it matches a food category, accept it
    for keyword in CATEGORY_MAP.keys():
        if keyword in text:
            return True

    # Third check: if it contains a known food brand, accept it
    for brand in KNOWN_BRANDS:
        if brand in text:
            return True

    # Default: accept (but it will go to Overig category)
    return True


def extract_brand_from_name(name):
    """Extract brand from product name."""
    name_lower = name.lower()
    for brand in KNOWN_BRANDS:
        if brand in name_lower:
            # Proper capitalization
            if brand == 'coca-cola' or brand == 'coca cola':
                return 'Coca-Cola'
            elif brand == 'lay\'s' or brand == 'lays':
                return "Lay's"
            elif brand == 'calvé' or brand == 'calve':
                return 'Calvé'
            elif brand == 'nescafé' or brand == 'nescafe':
                return 'Nescafé'
            elif brand == 'de ruijter':
                return 'De Ruijter'
            else:
                return brand.title()
    return ''


def get_folder_metadata():
    """Get folder metadata from Schwarz API."""
    # Try to find current week folder
    now = datetime.now()
    week = now.isocalendar()[1]
    year = now.year

    slug = f"hah-wk{week}-{year}"

    try:
        response = requests.get(f"{SCHWARZ_API}?flyer_identifier={slug}&region_id=0", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                flyer = data.get('flyer', {})
                return {
                    'name': flyer.get('name', ''),
                    'title': flyer.get('title', ''),
                    'start_date': flyer.get('offerStartDate', ''),
                    'end_date': flyer.get('offerEndDate', ''),
                    'pdf_url': flyer.get('pdfUrl', ''),
                }
    except Exception as e:
        print(f"  Warning: Could not fetch Schwarz API: {e}")

    return {}


def collect_products_from_lidl(page):
    """Collect products from Lidl.nl offers page."""
    print("  Scrolling to load all products...")

    for i in range(15):
        page.evaluate("window.scrollBy(0, 800)")
        time.sleep(0.3)

    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(2)

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
                match = re.search(r'/p(\d+)', href)
                product_id = match.group(1) if match else str(abs(hash(href)))

                products.append({
                    'id': f"lidl-{product_id}",
                    'name': name,
                    'product_url': full_url,
                })

    return products


def fetch_product_details(page, product):
    """Fetch detailed info from product page."""
    url = product.get('product_url')
    if not url:
        return product

    try:
        page.goto(url, wait_until='domcontentloaded', timeout=15000)
        time.sleep(0.3)

        json_ld_elements = page.query_selector_all('script[type="application/ld+json"]')

        for json_ld in json_ld_elements:
            try:
                data = json.loads(json_ld.inner_text())
                if data.get('@type') == 'Product':
                    product['name'] = data.get('name', product.get('name', ''))

                    brand_info = data.get('brand', {})
                    if isinstance(brand_info, dict):
                        product['brand'] = brand_info.get('name', '')

                    product['sku'] = data.get('sku', '')

                    images = data.get('image', [])
                    if images:
                        product['image_url'] = images[0] if isinstance(images, list) else images

                    offers = data.get('offers', [])
                    if offers:
                        offer = offers[0] if isinstance(offers, list) else offers
                        product['price'] = offer.get('price')
                        product['currency'] = offer.get('priceCurrency', 'EUR')

                    rating = data.get('aggregateRating', {})
                    if rating:
                        product['rating'] = rating.get('ratingValue')
                        product['rating_count'] = rating.get('ratingCount')

                    break
            except json.JSONDecodeError:
                continue

    except Exception as e:
        print(f"    Warning: {str(e)[:40]}")

    return product


def collect_from_backup_source():
    """Collect products from supermarktaanbiedingen.com as backup."""
    print("  Fetching from backup source...")

    products = []

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0',
        }
        response = requests.get(BACKUP_SOURCE, headers=headers, timeout=30)
        html = response.text

        # Extract products
        product_blocks = re.findall(r'<li id="product-([^"]+)"[^>]*>(.*?)</li>', html, re.DOTALL)

        seen_names = set()
        for slug, block in product_blocks:
            title_match = re.search(r'title="([^"]+)"', block)
            name = title_match.group(1) if title_match else slug.replace('-', ' ').title()

            name_key = name.lower().strip()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            price_match = re.search(r'card_prijs">([0-9]+[.,][0-9]{2})</span>', block)
            price = None
            if price_match:
                price = float(price_match.group(1).replace(',', '.'))

            old_price_match = re.search(r'card_prijs-oud">\s*([0-9]+[.,][0-9]{2})</span>', block)
            original_price = None
            if old_price_match:
                original_price = float(old_price_match.group(1).replace(',', '.'))

            discount_text = ""
            if price and original_price and original_price > price:
                discount_pct = round((1 - price / original_price) * 100)
                discount_text = f"-{discount_pct}%"

            img_match = re.search(r'<img[^>]+src="([^"]+)"', block)
            image_url = img_match.group(1) if img_match else ""
            if image_url and not image_url.startswith('http'):
                image_url = f"https://www.supermarktaanbiedingen.com{image_url}"

            href_match = re.search(r'href="(/aanbieding/[^"]+)"', block)
            product_url = ""
            if href_match:
                product_url = f"https://www.supermarktaanbiedingen.com{href_match.group(1)}"

            products.append({
                'id': f"lidl-backup-{slug}",
                'name': name,
                'price': price,
                'original_price': original_price,
                'discount_text': discount_text,
                'image_url': image_url,
                'product_url': product_url,
                'source': 'supermarktaanbiedingen.com',
            })

        print(f"    Found {len(products)} products from backup source")

    except Exception as e:
        print(f"    Warning: Backup source failed: {e}")

    return products


def main(test_mode=False):
    print("=" * 60)
    print("Lidl Folder Extractor (Hybrid)")
    print("=" * 60)

    # Get folder metadata
    print("\nStep 1: Getting folder metadata from Schwarz API...")
    folder_info = get_folder_metadata()
    if folder_info:
        print(f"  Folder: {folder_info.get('name')} - {folder_info.get('title')}")
        print(f"  Valid: {folder_info.get('start_date')} to {folder_info.get('end_date')}")

    all_products = []
    seen_names = set()

    # Primary source: Lidl.nl with Playwright
    print("\nStep 2: Scraping Lidl.nl offers page...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0'
        )
        page = context.new_page()

        page.goto(OFFERS_URL, wait_until='networkidle', timeout=60000)

        try:
            page.click('button:has-text("Accepteren")', timeout=5000)
            time.sleep(2)
        except:
            pass

        time.sleep(5)

        products = collect_products_from_lidl(page)
        print(f"  Found {len(products)} products on offers page")

        # Filter to food only
        food_products = [p for p in products if is_food_product(p.get('name', ''), p.get('product_url', ''))]
        print(f"  Filtered to {len(food_products)} food products")

        if test_mode:
            food_products = food_products[:10]
            print(f"  Test mode: processing only {len(food_products)} products")

        # Fetch details for each product
        print(f"\nStep 3: Fetching details for {len(food_products)} products...")
        for i, product in enumerate(food_products):
            print(f"  [{i+1}/{len(food_products)}] {product.get('name', 'Unknown')[:45]}")
            product = fetch_product_details(page, product)

            # Extract brand if not set
            if not product.get('brand'):
                product['brand'] = extract_brand_from_name(product.get('name', ''))

            # Categorize
            product['category'] = categorize_product(product.get('name', ''), product.get('product_url', ''))

            # Set defaults
            product.setdefault('brand', '')
            product.setdefault('price', None)
            product.setdefault('original_price', None)
            product.setdefault('discount_text', '')
            product.setdefault('image_url', '')
            product.setdefault('currency', '€')
            product['source'] = 'lidl.nl'

            seen_names.add(product.get('name', '').lower().strip())
            all_products.append(product)

        browser.close()

    # Backup source: supermarktaanbiedingen.com
    print("\nStep 4: Checking backup source for additional products...")
    backup_products = collect_from_backup_source()

    added_from_backup = 0
    for bp in backup_products:
        name_key = bp.get('name', '').lower().strip()
        if name_key not in seen_names and is_food_product(bp.get('name', ''), bp.get('product_url', '')):
            bp['category'] = categorize_product(bp.get('name', ''), bp.get('product_url', ''))
            bp['brand'] = extract_brand_from_name(bp.get('name', ''))
            bp.setdefault('currency', '€')
            all_products.append(bp)
            seen_names.add(name_key)
            added_from_backup += 1

    print(f"  Added {added_from_backup} additional products from backup source")

    # Build output
    now = datetime.now()
    folder_week = f"week-{now.isocalendar()[1]}-{now.year}"

    output = {
        'supermarket': 'Lidl',
        'folder_week': folder_week,
        'extracted_at': now.isoformat(),
        'source_url': OFFERS_URL,
        'extraction_method': 'hybrid',
        'folder_info': folder_info,
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
    archive_file = f"{archive_dir}/folder_data_week_{week_num}_lidl_hybrid.json"
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\n{'=' * 60}")
    print("Extraction complete!")
    print(f"{'=' * 60}")
    print(f"Total food products: {len(all_products)}")
    print(f"With prices: {sum(1 for p in all_products if p.get('price'))}")
    print(f"With brands: {sum(1 for p in all_products if p.get('brand'))}")
    print(f"With images: {sum(1 for p in all_products if p.get('image_url'))}")
    print(f"Output saved to: {OUTPUT_FILE}")

    # Categories
    categories = {}
    for p in all_products:
        cat = p.get('category', 'Overig')
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\n--- Products by Category ---")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Sample products with good data
    print(f"\n--- Sample Products ---")
    good_products = [p for p in all_products if p.get('price') and p.get('brand')]
    for p in (good_products or all_products)[:5]:
        price = f"€{p['price']:.2f}" if p.get('price') else "N/A"
        brand = p.get('brand', '-') or '-'
        print(f"  {p['name'][:40]:40} | {brand[:15]:15} | {price}")

    return output


if __name__ == "__main__":
    import sys
    test_mode = '--test' in sys.argv
    main(test_mode=test_mode)
