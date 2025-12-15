"""
Lidl Folder Extractor

Extracts food product offers from Lidl's weekly folder.

Primary source: supermarktaanbiedingen.com (aggregates Lidl food offers)
Secondary source: leaflets.schwarz API (for non-food items and folder metadata)

Note: Lidl's official API only returns non-food products (clothing, tools, home items).
Food products are only available through third-party aggregators.

Data extracted per product:
- name, brand (if available)
- price (current and original)
- discount percentage
- category
- image URL
- product URL
"""

import json
import requests
import re
from datetime import datetime
from html import unescape

OUTPUT_FILE = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/lidl/folder_data.json"

# Primary source for food products
FOOD_SOURCE_URL = "https://www.supermarktaanbiedingen.com/aanbiedingen/lidl"

# Secondary source for folder metadata and non-food products
FOLDERS_PAGE = "https://www.lidl.nl/c/service-contact-folders/s10008124"
API_BASE = "https://endpoints.leaflets.schwarz/v4/flyer"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
}


def extract_food_products():
    """Extract food products from supermarktaanbiedingen.com."""
    print("Fetching food products from supermarktaanbiedingen.com...")

    response = requests.get(FOOD_SOURCE_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text

    products = []
    seen_names = set()

    # Extract product data using regex patterns
    # Pattern: id="product-SLUG"...title="NAME"...card_prijs-oud">OLD_PRICE</span><span class="card_prijs">PRICE</span>
    # Also capture image URL

    # First, find all product blocks
    product_blocks = re.findall(
        r'<li id="product-([^"]+)"[^>]*>(.*?)</li>',
        html, re.DOTALL
    )

    print(f"  Found {len(product_blocks)} product blocks")

    for slug, block in product_blocks:
        # Extract product name from title attribute
        title_match = re.search(r'title="([^"]+)"', block)
        name = title_match.group(1) if title_match else slug.replace('-', ' ').title()

        # Skip duplicates (page shows some products twice)
        name_key = name.lower().strip()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        # Extract current price
        price_match = re.search(r'card_prijs">([0-9]+[.,][0-9]{2})</span>', block)
        price = None
        if price_match:
            price_str = price_match.group(1).replace(',', '.')
            try:
                price = float(price_str)
            except ValueError:
                pass

        # Extract original price (if discounted)
        # Note: old price may have leading space or &nbsp;
        old_price_match = re.search(r'card_prijs-oud">\s*([0-9]+[.,][0-9]{2})</span>', block)
        original_price = None
        if old_price_match:
            old_price_str = old_price_match.group(1).replace(',', '.')
            try:
                original_price = float(old_price_str)
            except ValueError:
                pass

        # Calculate discount percentage
        discount_text = ""
        if price and original_price and original_price > price:
            discount_pct = round((1 - price / original_price) * 100)
            discount_text = f"-{discount_pct}%"

        # Extract image URL
        img_match = re.search(r'<img[^>]+src="([^"]+)"', block)
        image_url = img_match.group(1) if img_match else ""
        if image_url and not image_url.startswith('http'):
            image_url = f"https://www.supermarktaanbiedingen.com{image_url}"

        # Extract product URL
        href_match = re.search(r'href="(/aanbieding/[^"]+)"', block)
        product_url = ""
        if href_match:
            product_url = f"https://www.supermarktaanbiedingen.com{href_match.group(1)}"

        # Determine category based on product name
        category = categorize_product(name)

        product = {
            'id': f"lidl-{slug}",
            'name': name,
            'brand': '',  # Not available from this source
            'price': price,
            'original_price': original_price,
            'discount_text': discount_text,
            'currency': '€',
            'category': category,
            'image_url': image_url,
            'product_url': product_url,
            'source': 'supermarktaanbiedingen.com',
        }

        products.append(product)

    print(f"  Extracted {len(products)} unique food products")
    return products


def categorize_product(name):
    """Categorize product based on name keywords."""
    name_lower = name.lower()

    categories = {
        'Groente & Fruit': ['appel', 'peer', 'banaan', 'sinaas', 'mandarijn', 'druif', 'meloen',
                           'aardbei', 'framboos', 'tomaat', 'komkommer', 'paprika', 'ui', 'aardappel',
                           'wortel', 'sla', 'spinazie', 'broccoli', 'bloemkool', 'prei', 'champignon',
                           'avocado', 'lychee', 'pompoen', 'spruitjes', 'groente', 'fruit', 'kool'],
        'Zuivel & Eieren': ['melk', 'yoghurt', 'kaas', 'boter', 'ei', 'room', 'kwark', 'vla',
                           'margarine', 'zuivel', 'campina', 'almhof', 'optimel'],
        'Vlees & Vis': ['kip', 'varken', 'rund', 'gehakt', 'worst', 'ham', 'spek', 'bacon',
                       'zalm', 'vis', 'garnaal', 'tonijn', 'haring', 'makreel', 'filet',
                       'schnit', 'burger', 'vlees'],
        'Brood & Gebak': ['brood', 'stok', 'croissant', 'cake', 'koek', 'gebak', 'taart',
                         'donut', 'muffin', 'brownie', 'stol', 'broodje', 'bol'],
        'Dranken': ['cola', 'fanta', 'sprite', 'sap', 'water', 'thee', 'koffie', 'bier',
                   'wijn', 'frisdrank', 'limonade', 'energy', 'ice tea', 'drink'],
        'Snacks & Zoetwaren': ['chips', 'nootjes', 'chocola', 'snoep', 'koek', 'biscuit',
                               'drop', 'popcorn', 'borrel', 'cracker'],
        'Diepvries': ['diepvries', 'ijs', 'pizza', 'friet', 'kroket', 'snack'],
        'Houdbaar': ['pasta', 'rijst', 'saus', 'soep', 'conserv', 'olie', 'azijn',
                    'mayonaise', 'ketchup', 'mosterd', 'pindakaas', 'jam', 'honing'],
    }

    for category, keywords in categories.items():
        if any(kw in name_lower for kw in keywords):
            return category

    return 'Overig'


def get_current_folder_slugs():
    """Fetch the current folder slugs from Lidl's folder page."""
    print("Fetching folder metadata from Lidl...")

    response = requests.get(FOLDERS_PAGE, headers=HEADERS, timeout=30)
    response.raise_for_status()

    # Find folder slugs like hah-wk50-2025
    pattern = r'hah-wk\d+-[a-z0-9-]+'
    slugs = list(set(re.findall(pattern, response.text)))

    # Separate food folder (no -nf) from non-food folder (-nf)
    food_slugs = [s for s in slugs if '-nf-' not in s]
    nonfood_slugs = [s for s in slugs if '-nf-' in s]

    return food_slugs, nonfood_slugs


def fetch_folder_metadata(slug):
    """Fetch folder metadata from the leaflets.schwarz API."""
    url = f"{API_BASE}?flyer_identifier={slug}&region_id=0"

    try:
        response = requests.get(url, headers={
            'User-Agent': HEADERS['User-Agent'],
            'Accept': 'application/json',
            'Accept-Encoding': 'identity',
        }, timeout=30)
        response.raise_for_status()

        data = response.json()
        if not data.get('success'):
            return None

        flyer = data.get('flyer', {})
        return {
            'name': flyer.get('name', ''),
            'title': flyer.get('title', ''),
            'start_date': flyer.get('offerStartDate', flyer.get('startDate', '')),
            'end_date': flyer.get('offerEndDate', flyer.get('endDate', '')),
            'pdf_url': flyer.get('pdfUrl', ''),
            'folder_url': flyer.get('flyerUrlAbsolute', ''),
        }
    except Exception as e:
        print(f"  Warning: Could not fetch folder metadata: {e}")
        return None


def main():
    print("=" * 60)
    print("Lidl Folder Extractor")
    print("=" * 60)

    # Get folder metadata
    food_slugs, _ = get_current_folder_slugs()
    folder_info = {}
    if food_slugs:
        print(f"  Found folder slugs: {food_slugs}")
        folder_info = fetch_folder_metadata(food_slugs[0]) or {}

    # Extract food products from supermarktaanbiedingen.com
    food_products = extract_food_products()

    # Filter to only food products (exclude flowers, plants, non-food)
    non_food_keywords = ['kerstster', 'orchidee', 'amaryllis', 'ilex', 'katjes', 'kerststuk',
                         'nordmann', 'kerstarrangement', 'takken', 'bloem', 'plant']

    filtered_products = []
    for p in food_products:
        name_lower = p['name'].lower()
        if not any(kw in name_lower for kw in non_food_keywords):
            filtered_products.append(p)

    print(f"  Filtered to {len(filtered_products)} food products (excluded {len(food_products) - len(filtered_products)} non-food)")

    # Data validation - minimum product count check
    MIN_PRODUCTS = 30  # Lidl typically has 40-80 food products
    if len(filtered_products) < MIN_PRODUCTS:
        raise ValueError(f"VALIDATION FAILED: Lidl returned only {len(filtered_products)} products (minimum: {MIN_PRODUCTS}). Website may have changed.")

    # Determine folder week
    now = datetime.now()
    folder_week = f"week-{now.isocalendar()[1]}-{now.year}"

    # Build output
    output = {
        'supermarket': 'Lidl',
        'folder_week': folder_week,
        'extracted_at': now.isoformat(),
        'source_url': FOOD_SOURCE_URL,
        'folder_info': folder_info,
        'product_count': len(filtered_products),
        'products': filtered_products,
    }

    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Archive copy with week number
    import os
    week_num = now.isocalendar()[1]
    archive_dir = os.path.dirname(OUTPUT_FILE) + '/archive'
    os.makedirs(archive_dir, exist_ok=True)
    archive_file = f"{archive_dir}/folder_data_week_{week_num}_lidl.json"
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Archived to: {archive_file}")

    # Print summary
    print(f"\n{'=' * 60}")
    print("Extraction complete!")
    print(f"{'=' * 60}")
    if folder_info:
        print(f"Folder: {folder_info.get('name', 'Unknown')} - {folder_info.get('title', '')}")
        print(f"Valid: {folder_info.get('start_date', '')} to {folder_info.get('end_date', '')}")
    print(f"Total food products: {len(filtered_products)}")
    print(f"With prices: {sum(1 for p in filtered_products if p.get('price'))}")
    print(f"With discounts: {sum(1 for p in filtered_products if p.get('discount_text'))}")
    print(f"With images: {sum(1 for p in filtered_products if p.get('image_url'))}")
    print(f"Output saved to: {OUTPUT_FILE}")

    # Show sample products by category
    categories = {}
    for p in filtered_products:
        cat = p.get('category', 'Overig')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)

    print(f"\n--- Products by Category ---")
    for cat, prods in sorted(categories.items()):
        print(f"\n{cat} ({len(prods)} products):")
        for p in prods[:3]:
            discount = p.get('discount_text', '')
            price = p.get('price')
            price_str = f"€{price:>5.2f}" if price else "N/A"
            orig = f" (was €{p.get('original_price'):.2f})" if p.get('original_price') else ""
            print(f"  {p.get('name', 'N/A')[:35]:35} | {price_str}{orig} {discount}")

    return output


if __name__ == "__main__":
    main()
