"""
Albert Heijn Bonus Folder Extractor

Extracts products from the actual AH bonus folder (Publitas).
This gives us only the products that appear in the weekly folder,
not all bonus products from the API.

Approach:
1. Get folder hotspot URLs from Publitas
2. Extract product info from hotspot titles and folder text
3. Use AH search API to get full product details for each item
"""

import requests
import json
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Publitas folder settings
PUBLITAS_BASE = "https://view.publitas.com"
AH_GROUP = "ah-nl"

# AH API settings
AUTH_URL = "https://api.ah.nl/mobile-auth/v1/auth/token/anonymous"
SEARCH_URL = "https://api.ah.nl/mobile-services/product/search/v2"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Cache for API token
_api_token = None

# Non-food categories to exclude
NON_FOOD_CATEGORIES = [
    'Huishouden',
    'AH Voordeelshop',
    'Drogisterij',
    'Huisdier',
    'Baby',
]

# Keywords in hotspot titles that indicate non-food products (skip fetching)
NON_FOOD_KEYWORDS = [
    'schoonmaak', 'wasmiddel', 'vaatwas', 'luchtverfriss', 'toiletpapier',
    'huisdier', 'hond', 'kat', 'voer',
    'shampoo', 'douche', 'deodorant', 'tandpasta', 'zeep', 'verzorging',
    'luiers', 'baby', 'billendoekjes',
    'batterij', 'lamp', 'kerstverlichting', 'kaarsen',
    'pannen', 'bestek', 'servies', 'keukengerei',
    'gamingstoel', 'gamebureau', 'headset', 'toetsenbord',
    'airfryer', 'friteuse', 'grill', 'braadpan', 'mixer', 'keukenmachine',
    'parfum', 'giftset', 'cadeaukaart',
    'kamado', 'bbq',
]


def get_current_folder_slug():
    """Get the current bonus folder slug from AH website."""
    # Fetch AH bonus folder page to find the Publitas slug
    response = requests.get(
        "https://www.ah.nl/bonus/folder",
        headers=HEADERS,
        timeout=30
    )

    # Look for bonus-week-XX-YYYY pattern in the page
    match = re.search(r'"slug":"(bonus-week-\d+-\d+)"', response.text)
    if match:
        return match.group(1)

    # Fallback: construct from current week
    now = datetime.now()
    week = now.isocalendar()[1]
    return f"bonus-week-{week}-{now.year}"


def get_folder_data(slug):
    """Get folder metadata including page count and text content."""
    url = f"{PUBLITAS_BASE}/{AH_GROUP}/{slug}/data.json"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def get_hotspots_for_page(slug, page_num):
    """Get hotspots (product links) for a specific page."""
    url = f"{PUBLITAS_BASE}/{AH_GROUP}/{slug}/page/{page_num}/hotspots_data.json"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return []


def is_non_food_hotspot(title):
    """Check if a hotspot title indicates a non-food product."""
    if not title:
        return False
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in NON_FOOD_KEYWORDS)


def get_all_bonus_urls(slug, total_pages):
    """Get all unique bonus product URLs and titles from the folder."""
    all_items = {}  # url -> title
    skipped_non_food = 0

    print(f"Fetching hotspots from {total_pages} pages...")

    # Fetch hotspots from each page
    for page in range(1, total_pages + 1):
        hotspots = get_hotspots_for_page(slug, page)
        for h in hotspots:
            if h.get('type') == 'externalLink' and h.get('url'):
                url = h['url']
                title = h.get('title', '')
                # Look for bonus/groep URLs
                if '/bonus/groep/' in url or '/producten/product/' in url:
                    # Skip non-food products based on hotspot title
                    if is_non_food_hotspot(title):
                        skipped_non_food += 1
                        continue
                    all_items[url] = title

    print(f"Skipped {skipped_non_food} non-food hotspots based on keywords")
    return all_items


def get_api_token():
    """Get or reuse AH API token."""
    global _api_token
    if _api_token:
        return _api_token

    response = requests.post(
        AUTH_URL,
        headers={"Content-Type": "application/json"},
        json={"clientId": "appie"}
    )
    response.raise_for_status()
    _api_token = response.json()["access_token"]
    return _api_token


def search_product_by_name(query):
    """Search for a product in AH API by name."""
    try:
        token = get_api_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application": "AHWEBSHOP"
        }

        # Clean up query - remove "Bekijk" prefix and common words
        query = query.replace('Bekijk ', '').replace('Alle ', '')

        params = {
            "query": query,
            "sortOn": "RELEVANCE",
            "page": 0,
            "size": 5  # Just get top results
        }

        response = requests.get(SEARCH_URL, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            products = data.get("products", [])
            # Filter for bonus products only
            bonus_products = [p for p in products if p.get("isBonus")]
            return bonus_products
    except Exception:
        pass
    return []


def is_food_product(product):
    """Check if a product is a food item (not household, pet, etc.)."""
    category = product.get("mainCategory", "") or ""
    return category not in NON_FOOD_CATEGORIES


def calculate_offer_price_from_mechanism(bonus_mechanism, normal_price):
    """Calculate effective offer price from bonus mechanism.

    Examples:
    - "2e gratis" or "1+1 gratis" -> 50% off (half price per item)
    - "2e halve prijs" -> 25% off (0.75x per item)
    - "3 + 1 gratis" -> 25% off (3/4 price per item)
    - "2 + 1 gratis" -> 33% off (2/3 price per item)
    - "5 + 1 gratis" -> ~17% off (5/6 price per item)
    - "25% korting" -> 25% off
    - "2 voor X.XX" -> X.XX / 2 per item
    - "VOOR X.XX" -> X.XX fixed price
    - "2 stapelen voor X.XX" -> X.XX / 2 per item
    """
    if not bonus_mechanism or not normal_price:
        return None

    mechanism = bonus_mechanism.lower().strip()

    # Pattern: "1+1 gratis" or "2e gratis"
    if '1+1' in mechanism or '2e gratis' in mechanism or '1 + 1' in mechanism:
        return round(normal_price * 0.5, 2)

    # Pattern: "N + 1 gratis" (generic: buy N, get 1 free -> pay N out of N+1)
    n_plus_1_match = re.search(r'(\d+)\s*\+\s*1\s*gratis', mechanism)
    if n_plus_1_match:
        n = int(n_plus_1_match.group(1))
        return round(normal_price * (n / (n + 1)), 2)

    # Pattern: "2e halve prijs"
    if '2e halve prijs' in mechanism or 'tweede halve prijs' in mechanism:
        return round(normal_price * 0.75, 2)

    # Pattern: "XX% korting"
    pct_match = re.search(r'(\d+)\s*%\s*korting', mechanism)
    if pct_match:
        discount_pct = int(pct_match.group(1))
        return round(normal_price * (1 - discount_pct / 100), 2)

    # Pattern: "N stapelen voor X.XX" or "N voor X.XX"
    stapel_match = re.search(r'(\d+)\s*(?:stapelen\s+)?voor\s*(\d+)[,.](\d{2})', mechanism)
    if stapel_match:
        quantity = int(stapel_match.group(1))
        total_price = float(f"{stapel_match.group(2)}.{stapel_match.group(3)}")
        return round(total_price / quantity, 2)

    # Pattern: "VOOR X.XX" (fixed price, no quantity prefix)
    fixed_match = re.search(r'^voor\s*(\d+)[,.](\d{2})$', mechanism)
    if fixed_match:
        return float(f"{fixed_match.group(1)}.{fixed_match.group(2)}")

    return None


def transform_api_product(p, source_url=''):
    """Transform AH API product to standard format."""
    # Get best image URL (prefer 400x400)
    images = p.get("images", [])
    image_url = None
    for img in images:
        if img.get("width") == 400:
            image_url = img.get("url")
            break
    if not image_url and images:
        image_url = images[0].get("url")

    # Get discount info
    discount_labels = p.get("discountLabels", [])
    discount_description = None
    if discount_labels:
        discount_description = discount_labels[0].get("defaultDescription")

    # Get bonus mechanism
    bonus_mechanism = p.get("bonusMechanism", discount_description or "")

    # Calculate discount
    current_price = p.get("currentPrice")
    original_price = p.get("priceBeforeBonus")

    # If no current price but have bonus mechanism, calculate it
    if not current_price and original_price and bonus_mechanism:
        current_price = calculate_offer_price_from_mechanism(bonus_mechanism, original_price)

    discount_pct = None
    if current_price and original_price and original_price > current_price:
        discount_pct = round((1 - current_price / original_price) * 100, 1)

    return {
        "id": str(p.get("webshopId", "")),
        "name": p.get("title", ""),
        "brand": p.get("brand", ""),
        "offer_price": current_price,
        "normal_price": original_price,
        "discount_percent": discount_pct,
        "bonus_mechanism": bonus_mechanism,
        "unit_size": p.get("salesUnitSize", ""),
        "image_url": image_url,
        "product_url": source_url or f"https://www.ah.nl/producten/product/{p.get('webshopId', '')}",
        "category": p.get("mainCategory", ""),
        "nutriscore": p.get("nutriscore", ""),
        "bonus_start": p.get("bonusStartDate", ""),
        "bonus_end": p.get("bonusEndDate", "")
    }


def fetch_bonus_group_products(url):
    """Fetch products from a bonus group URL."""
    try:
        # Extract group ID from URL like /bonus/groep/759984?week=50
        match = re.search(r'/bonus/groep/(\d+)', url)
        if not match:
            return []

        group_id = match.group(1)

        # Fetch the bonus group page
        response = requests.get(url, headers=HEADERS, timeout=15)
        html = response.text

        products = []

        # Extract product data from the page
        # Look for JSON data embedded in the page
        json_match = re.search(r'window\["__APOLLO_STATE_BONUS__"\]\s*=\s*(\{.*?\});', html, re.DOTALL)
        if json_match:
            try:
                apollo_data = json.loads(json_match.group(1))

                # Extract products from Apollo state
                for key, value in apollo_data.items():
                    if key.startswith('Product:') and isinstance(value, dict):
                        prod = extract_product_from_apollo(value, apollo_data)
                        if prod:
                            prod['bonus_group_id'] = group_id
                            prod['source_url'] = url
                            products.append(prod)

            except json.JSONDecodeError:
                pass

        # If Apollo state didn't work, try simpler extraction
        if not products:
            # Extract from embedded JSON in script tags
            data_matches = re.findall(r'"title":"([^"]+)".*?"currentPrice":(\d+\.?\d*).*?"webshopId":"?(\d+)"?', html)
            for title, price, webshop_id in data_matches:
                products.append({
                    'id': webshop_id,
                    'name': title.replace('\\u0026', '&'),
                    'offer_price': float(price),
                    'bonus_group_id': group_id,
                    'source_url': url
                })

        return products

    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return []


def extract_product_from_apollo(product, apollo_data):
    """Extract product info from Apollo state data."""
    try:
        # Get nested references
        def resolve_ref(ref):
            if isinstance(ref, dict) and '__ref' in ref:
                return apollo_data.get(ref['__ref'], {})
            return ref

        # Get images
        images = product.get('images', [])
        image_url = None
        if images:
            for img_ref in images:
                img = resolve_ref(img_ref)
                if isinstance(img, dict):
                    url = img.get('url')
                    if url and '400x400' in url:
                        image_url = url
                        break
                    elif url and not image_url:
                        image_url = url

        # Get price info
        price_info = resolve_ref(product.get('price', {}))
        current_price = price_info.get('now') if isinstance(price_info, dict) else None
        original_price = price_info.get('was') if isinstance(price_info, dict) else None

        # Get bonus info
        bonus = resolve_ref(product.get('bonus', {}))
        bonus_mechanism = bonus.get('bonusMechanism', '') if isinstance(bonus, dict) else ''

        return {
            'id': str(product.get('webshopId', '')),
            'name': product.get('title', ''),
            'brand': product.get('brand', ''),
            'offer_price': current_price,
            'normal_price': original_price,
            'bonus_mechanism': bonus_mechanism,
            'unit_size': product.get('salesUnitSize', ''),
            'image_url': image_url,
            'category': product.get('mainCategory', ''),
            'nutriscore': product.get('nutriscore', '')
        }
    except Exception:
        return None


def extract_from_page_text(folder_data):
    """Extract product info from OCR text on folder pages."""
    products = []

    for spread in folder_data.get('spreads', []):
        for page in spread.get('pages', []):
            text = page.get('text', '')
            page_num = page.get('number', 0)

            if not text:
                continue

            # Parse products from the text
            # Look for patterns like "Product name\nX.XX Y.YY" or "X% korting"
            lines = text.split('\n')

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                # Skip empty lines and page info
                if not line or line in ['Looptijd acties:', 'Voor 2e gratis geldt:']:
                    i += 1
                    continue

                # Look for product blocks
                # Typically: discount tag, product name, description, prices

                # Check for discount patterns (2e gratis, X% korting, etc.)
                discount_text = None
                if re.match(r'^(\d+%|2\s*gratis|1\+1|2e|e)$', line, re.IGNORECASE):
                    discount_text = line
                    i += 1
                    if i < len(lines) and lines[i].strip() in ['gratis', 'korting', 'e']:
                        discount_text += ' ' + lines[i].strip()
                        i += 1
                    continue

                # Look for price patterns: X.XX or X.XX Y.YY
                price_match = re.search(r'(\d+\.\d{2})\s+(\d+\.?\d*)', line)
                if price_match:
                    # This line has prices
                    i += 1
                    continue

                i += 1

    return products


def fetch_product_details_from_api(product_id):
    """Fetch detailed product info from AH API."""
    try:
        # Get anonymous token
        auth_response = requests.post(
            "https://api.ah.nl/mobile-auth/v1/auth/token/anonymous",
            headers={"Content-Type": "application/json"},
            json={"clientId": "appie"},
            timeout=10
        )
        token = auth_response.json().get("access_token")

        if not token:
            return None

        # Fetch product details
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Application": "AHWEBSHOP"
        }

        response = requests.get(
            f"https://api.ah.nl/mobile-services/product/detail/v4/fir/{product_id}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()

    except Exception:
        pass

    return None


def main():
    print("=" * 60)
    print("Albert Heijn Bonus Folder Extractor")
    print("=" * 60)

    # Get current folder slug
    print("\nFetching current bonus folder...")
    slug = get_current_folder_slug()
    print(f"Current folder: {slug}")

    # Parse week from slug (bonus-week-51-2025 -> week-51-2025)
    week_match = re.search(r'bonus-week-(\d+)-(\d+)', slug)
    folder_week = f"week-{week_match.group(1)}-{week_match.group(2)}" if week_match else None

    # Get folder data
    print("\nFetching folder data...")
    folder_data = get_folder_data(slug)

    # New Publitas API uses numPages directly instead of spreads array
    total_pages = folder_data.get('numPages', 0)

    # Fallback to old spreads format if present
    if total_pages == 0:
        spreads = folder_data.get('spreads', [])
        total_pages = len(spreads)

    print(f"Folder has {total_pages} pages")

    # Get all bonus product URLs and titles from hotspots
    bonus_items = get_all_bonus_urls(slug, total_pages)
    print(f"Found {len(bonus_items)} bonus product links")

    # Get API token first
    print("\nGetting AH API token...")
    try:
        get_api_token()
        print("Token received")
    except Exception as e:
        print(f"Warning: Could not get API token: {e}")

    # Search for each product title via API
    print("\nSearching for products via API...")
    all_products = []
    seen_ids = set()

    for i, (url, title) in enumerate(bonus_items.items()):
        if not title:
            continue

        # Search for this product
        api_products = search_product_by_name(title)

        for p in api_products:
            # Skip non-food products
            if not is_food_product(p):
                continue

            pid = str(p.get("webshopId", ""))
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                product = transform_api_product(p, url)
                all_products.append(product)

        if (i + 1) % 20 == 0:
            print(f"  Processed {i + 1}/{len(bonus_items)} items... ({len(all_products)} products)")

    print(f"\nExtracted {len(all_products)} unique products from folder")

    # Data validation - minimum product count check
    MIN_PRODUCTS = 40  # AH typically has 60-150 bonus products
    if len(all_products) < MIN_PRODUCTS:
        raise ValueError(f"VALIDATION FAILED: Albert Heijn returned only {len(all_products)} products (minimum: {MIN_PRODUCTS}). Website may have changed.")

    # Build output
    output = {
        'supermarket': 'Albert Heijn',
        'folder_week': folder_week,
        'extracted_at': datetime.now().isoformat(),
        'source_url': f'{PUBLITAS_BASE}/{AH_GROUP}/{slug}/',
        'folder_slug': slug,
        'product_count': len(all_products),
        'products': all_products
    }

    # Save
    import os
    output_file = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/ah/folder_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Archive copy with week number
    now = datetime.now()
    week_num = now.isocalendar()[1]
    archive_dir = os.path.dirname(output_file) + '/archive'
    os.makedirs(archive_dir, exist_ok=True)
    archive_file = f"{archive_dir}/folder_data_week_{week_num}_ah.json"
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Archived to: {archive_file}")

    print(f"\n{'=' * 60}")
    print(f"Extraction complete!")
    print(f"{'=' * 60}")
    print(f"Total products: {len(all_products)}")
    print(f"Products with images: {sum(1 for p in all_products if p.get('image_url'))}")
    print(f"Products with prices: {sum(1 for p in all_products if p.get('offer_price'))}")
    print(f"Output saved to: {output_file}")


if __name__ == "__main__":
    main()
