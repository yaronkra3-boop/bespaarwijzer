"""
Supermarket Aggregator

Combines all supermarket folder data into a single unified dataset.
Normalizes fields across different supermarket formats.
Generates insights and highlights.
"""

import json
import os
from datetime import datetime
from collections import defaultdict

BASE_PATH = "/Users/yaronkra/Jarvis/bespaarwijzer"
SCRAPERS_PATH = f"{BASE_PATH}/scrapers"
OUTPUT_FILE = f"{BASE_PATH}/pipeline/output/aggregated_data.json"


def load_dirk():
    """Load and normalize Dirk data.

    Expands products with multiple variants into individual products,
    each with an offer_group_id linking them together.
    """
    with open(f"{SCRAPERS_PATH}/dirk/folder_data.json", 'r') as f:
        data = json.load(f)

    products = []
    folder_validity = None

    for p in data.get('products', []):
        # Combine all package info for accurate type detection
        # unit_size often has multi-pack info like "4 x 1,5 liter"
        package_parts = [
            p.get('packaging', ''),
            p.get('unit_size', ''),
            p.get('weight', '')
        ]
        package_desc = ' '.join(part for part in package_parts if part)

        # Extract folder validity from first product with dates
        if not folder_validity and p.get('start_date') and p.get('end_date'):
            folder_validity = {
                'start_date': p.get('start_date', '').split('T')[0] if p.get('start_date') else '',
                'end_date': p.get('end_date', '').split('T')[0] if p.get('end_date') else ''
            }

        variants = p.get('variants', [])
        product_images = p.get('product_images', [])

        # If product has multiple variants, create individual products for each
        if len(variants) > 1:
            group_id = f"dirk_group_{p.get('id', '')}"

            for i, variant_name in enumerate(variants):
                # Use corresponding image if available, otherwise use main image
                variant_image = product_images[i] if i < len(product_images) else p.get('image_url', '')

                products.append({
                    'supermarket': 'Dirk',
                    'id': f"dirk_{p.get('id', '')}_{i+1}",
                    'name': variant_name,
                    'brand': p.get('brand', ''),
                    'package_description': package_desc,
                    'offer_price': p.get('offer_price'),
                    'normal_price': p.get('normal_price'),
                    'discount_text': p.get('discount_text', ''),
                    'category': p.get('category', ''),
                    'department': p.get('department', ''),
                    'webgroup': p.get('webgroup', ''),
                    'image_url': variant_image,
                    'source_url': p.get('product_url', ''),
                    'validity': f"{p.get('start_date', '')} - {p.get('end_date', '')}" if p.get('start_date') else '',
                    'is_vegetarian': False,
                    'is_biological': False,
                    'nutriscore': None,
                    'requires_card': False,
                    'offer_group_id': group_id,
                })
        else:
            # Single product or no variants - add as-is
            products.append({
                'supermarket': 'Dirk',
                'id': f"dirk_{p.get('id', '')}",
                'name': p.get('name', ''),
                'brand': p.get('brand', ''),
                'package_description': package_desc,
                'offer_price': p.get('offer_price'),
                'normal_price': p.get('normal_price'),
                'discount_text': p.get('discount_text', ''),
                'category': p.get('category', ''),
                'department': p.get('department', ''),
                'webgroup': p.get('webgroup', ''),
                'image_url': p.get('image_url', ''),
                'source_url': p.get('product_url', ''),
                'validity': f"{p.get('start_date', '')} - {p.get('end_date', '')}" if p.get('start_date') else '',
                'is_vegetarian': False,
                'is_biological': False,
                'nutriscore': None,
                'requires_card': False,
                'offer_group_id': None,
            })
    return products, data.get('folder_week', ''), folder_validity


def load_hoogvliet():
    """Load and normalize Hoogvliet data."""
    with open(f"{SCRAPERS_PATH}/hoogvliet/folder_data.json", 'r') as f:
        data = json.load(f)

    products = []

    # Hoogvliet folder week format is "week-50-2025", extract dates from folder URL or source
    # The folder URL contains the week number which we can use to derive dates
    folder_validity = None
    source_url = data.get('source_url', '')
    # Extract week from URL like "folder_2025_50" -> week 50 of 2025
    if 'folder_' in source_url:
        import re
        match = re.search(r'folder_(\d{4})_(\d+)', source_url)
        if match:
            year, week = int(match.group(1)), int(match.group(2))
            # Calculate week start/end dates (week starts on Monday in Netherlands)
            from datetime import datetime, timedelta
            # Get first day of the year and find the Monday of the given week
            first_day = datetime(year, 1, 1)
            # ISO week calculation
            week_start = first_day + timedelta(days=(week - 1) * 7 - first_day.weekday())
            week_end = week_start + timedelta(days=6)
            folder_validity = {
                'start_date': week_start.strftime('%Y-%m-%d'),
                'end_date': week_end.strftime('%Y-%m-%d')
            }

    for p in data.get('products', []):
        products.append({
            'supermarket': 'Hoogvliet',
            'id': f"hoogvliet_{p.get('id', '')}",
            'name': p.get('name', ''),
            'brand': p.get('brand', ''),
            'package_description': p.get('package_description', '') or p.get('unit', ''),
            'offer_price': p.get('offer_price'),
            'normal_price': p.get('normal_price'),
            'discount_text': p.get('discount_text', ''),
            'category': p.get('category', ''),
            'image_url': p.get('image_url', ''),
            'source_url': p.get('source_url', ''),
            'validity': '',
            'is_vegetarian': p.get('is_vegetarian', False),
            'is_biological': p.get('is_biological', False),
            'nutriscore': None,
            'requires_card': False,
            'offer_group_id': f"hoogvliet_{p.get('offer_group_id', '')}" if p.get('offer_group_id') else None
        })
    return products, data.get('folder_week', ''), folder_validity


def load_ah():
    """Load and normalize Albert Heijn data.

    Groups products by their bonus group URL (product_url contains /groep/XXXXX).
    Products in the same bonus group get an offer_group_id for variant grouping.
    """
    with open(f"{SCRAPERS_PATH}/ah/folder_data.json", 'r') as f:
        data = json.load(f)

    # First pass: count products per bonus group URL to identify multi-product groups
    url_counts = {}
    for p in data.get('products', []):
        url = p.get('product_url', '')
        if url:
            url_counts[url] = url_counts.get(url, 0) + 1

    products = []
    folder_validity = None

    for p in data.get('products', []):
        # Extract folder validity from first product with bonus dates
        if not folder_validity and p.get('bonus_start') and p.get('bonus_end'):
            folder_validity = {
                'start_date': p.get('bonus_start', ''),
                'end_date': p.get('bonus_end', '')
            }

        # Extract offer_group_id from product_url if this is a multi-product group
        # URL format: https://www.ah.nl/bonus/groep/753020?week=50
        product_url = p.get('product_url', '')
        offer_group_id = None
        if product_url and url_counts.get(product_url, 0) > 1:
            # Extract group number from URL
            import re
            match = re.search(r'/groep/(\d+)', product_url)
            if match:
                offer_group_id = f"ah_group_{match.group(1)}"

        products.append({
            'supermarket': 'Albert Heijn',
            'id': f"ah_{p.get('id', '')}",
            'name': p.get('name', ''),
            'brand': p.get('brand', ''),
            'package_description': p.get('unit_size', ''),
            'offer_price': p.get('offer_price'),
            'normal_price': p.get('normal_price'),
            'discount_text': p.get('bonus_mechanism', '') or (f"{p.get('discount_percent')}% korting" if p.get('discount_percent') else ''),
            'category': p.get('category', ''),
            'image_url': p.get('image_url', ''),
            'source_url': p.get('product_url', ''),
            'validity': f"{p.get('bonus_start', '')} - {p.get('bonus_end', '')}" if p.get('bonus_start') else '',
            'is_vegetarian': False,
            'is_biological': False,
            'nutriscore': p.get('nutriscore'),
            'requires_card': False,
            'offer_group_id': offer_group_id
        })
    return products, data.get('folder_week', ''), folder_validity


def parse_jumbo_discount_tag(discount_tag, regular_price):
    """Parse Jumbo discount tags and calculate the actual offer price per item.

    Examples:
    - "2 voor 5,00" -> 2.50 per item
    - "1+1 gratis" -> half price
    - "2e halve prijs" -> 0.75x regular price
    - "25% korting" -> 0.75x regular price

    Returns (offer_price_per_item, deal_description)
    """
    import re

    if not discount_tag or not regular_price:
        return regular_price, discount_tag

    tag_lower = discount_tag.lower().replace(',', '.')

    # Pattern: "X voor Y,ZZ" (e.g., "2 voor 5,00")
    match = re.search(r'(\d+)\s*voor\s*(\d+[.,]?\d*)', tag_lower)
    if match:
        quantity = int(match.group(1))
        total_price = float(match.group(2))
        return round(total_price / quantity, 2), discount_tag

    # Pattern: "1+1 gratis" or "2+1 gratis"
    match = re.search(r'(\d+)\s*\+\s*(\d+)\s*gratis', tag_lower)
    if match:
        buy = int(match.group(1))
        free = int(match.group(2))
        # Price per item = (buy * regular_price) / (buy + free)
        return round((buy * regular_price) / (buy + free), 2), discount_tag

    # Pattern: "2e halve prijs" (second at half price)
    if '2e halve prijs' in tag_lower or '2e voor halve prijs' in tag_lower:
        # Average price = (1 + 0.5) / 2 = 0.75
        return round(regular_price * 0.75, 2), discount_tag

    # Pattern: "2e gratis" (second free)
    if '2e gratis' in tag_lower:
        return round(regular_price / 2, 2), discount_tag

    # Pattern: "XX% korting"
    match = re.search(r'(\d+)\s*%\s*korting', tag_lower)
    if match:
        discount_pct = int(match.group(1))
        return round(regular_price * (1 - discount_pct / 100), 2), discount_tag

    # No pattern matched, return regular price
    return regular_price, discount_tag


def load_jumbo():
    """Load and normalize Jumbo data (v2 format with full product details).

    Groups products by brand + discount_tag + promo_title to reduce 500+ products
    to ~90 grouped promotions (same product with different flavors = 1 item).

    IMPORTANT: Parses discount_tag to calculate actual offer price (e.g., "2 voor 5,00" = €2.50 each)
    """
    with open(f"{SCRAPERS_PATH}/jumbo/folder_data.json", 'r') as f:
        data = json.load(f)

    raw_products = data.get('products', [])

    # Extract folder validity from first product's validity field
    # Jumbo format: "wo 10 t/m di 16 dec"
    folder_validity = None
    for p in raw_products:
        if p.get('validity'):
            # Parse "wo 10 t/m di 16 dec" format
            import re
            from datetime import datetime
            validity_text = p.get('validity', '')
            # Extract day numbers and month
            match = re.search(r'(\d+)\s+t/m\s+\w+\s+(\d+)\s+(\w+)', validity_text)
            if match:
                start_day, end_day, month_name = match.groups()
                month_map = {'jan': 1, 'feb': 2, 'mrt': 3, 'apr': 4, 'mei': 5, 'jun': 6,
                             'jul': 7, 'aug': 8, 'sep': 9, 'okt': 10, 'nov': 11, 'dec': 12}
                month = month_map.get(month_name.lower(), 12)
                year = datetime.now().year
                folder_validity = {
                    'start_date': f"{year}-{month:02d}-{int(start_day):02d}",
                    'end_date': f"{year}-{month:02d}-{int(end_day):02d}"
                }
            break

    # Group products by brand + discount_tag + promo_title to identify grouped offers
    groups = defaultdict(list)
    for p in raw_products:
        key = (
            p.get('brand', '') or 'Onbekend',
            p.get('discount_tag', '') or 'Geen aanbieding',
            p.get('promo_title', '') or p.get('name', '')
        )
        groups[key].append(p)

    # Create individual products with offer_group_id for grouped offers
    products = []
    for (brand, discount_tag, promo_title), prods in groups.items():
        # Generate a group ID based on the first product
        rep = next((p for p in prods if p.get('image_url')), prods[0])
        group_id = f"jumbo_group_{rep.get('id', '')}"

        # Create individual product entries for each variant
        for i, p in enumerate(prods):
            # Calculate actual offer price by parsing discount tag
            regular_price = p.get('offer_price') or p.get('normal_price')
            actual_price = regular_price
            if regular_price:
                actual_price, _ = parse_jumbo_discount_tag(discount_tag, regular_price)

            products.append({
                'supermarket': 'Jumbo',
                'id': f"jumbo_{p.get('id', '')}",
                'name': p.get('name', ''),
                'brand': brand if brand != 'Onbekend' else '',
                'package_description': p.get('unit_size', '') or p.get('subtitle', ''),
                'offer_price': actual_price,
                'normal_price': regular_price,
                'discount_text': discount_tag,
                'category': p.get('category', ''),
                'image_url': p.get('image_url', ''),
                'source_url': p.get('source_url', '') or p.get('url', ''),
                'validity': p.get('validity', ''),
                'is_vegetarian': False,
                'is_biological': False,
                'nutriscore': None,
                'requires_card': False,
                'price_per_unit': p.get('price_per_unit'),
                'price_unit': p.get('price_unit', ''),
                # Add offer_group_id only if this is part of a group with multiple products
                'offer_group_id': group_id if len(prods) > 1 else None,
            })

    # Sort by offer_group_id to keep grouped products together, then by name
    products.sort(key=lambda x: (x.get('offer_group_id') or '', x.get('name', '')))

    return products, data.get('folder_week', ''), folder_validity


def load_lidl():
    """Load and normalize Lidl data from folder_data.json (GridBox extraction).

    Uses folder_data.json which extracts products from Lidl.nl's gridbox impressions.
    Gets folder dates from the Schwarz Leaflets API.
    Includes discount data, original prices, Lidl Plus indicators, and product variants.

    Products with multiple variants are expanded into individual products,
    each with an offer_group_id linking them together (similar to Dirk).
    """
    with open(f"{SCRAPERS_PATH}/lidl/folder_data.json", 'r') as f:
        data = json.load(f)

    # Extract folder validity from folder_info
    folder_validity = None
    folder_info = data.get('folder_info', {})
    if folder_info.get('start_date') and folder_info.get('end_date'):
        folder_validity = {
            'start_date': folder_info.get('start_date', ''),
            'end_date': folder_info.get('end_date', '')
        }

    products = []
    for p in data.get('products', []):
        # Skip non-food products (legacy field from old scraper)
        if p.get('is_nonfood'):
            continue

        # Build package description from unit_size if available
        package_desc = p.get('unit_size', '') or p.get('basic_price', '')

        # Base product data (shared between main product and variants)
        base_data = {
            'supermarket': 'Lidl',
            'brand': p.get('brand', ''),
            'package_description': package_desc,
            'offer_price': p.get('price'),
            'normal_price': p.get('original_price'),
            'discount_text': p.get('discount_text', ''),
            'discount_percent': p.get('discount_percent'),
            'category': p.get('category', ''),
            'image_url': p.get('image_url', ''),
            'source_url': p.get('product_url', ''),
            'validity': '',
            'is_vegetarian': False,
            'is_biological': False,
            'nutriscore': None,
            'requires_card': p.get('is_lidl_plus', False)  # Lidl Plus offers need card
        }

        variants = p.get('variants', [])

        # If product has multiple variants, create individual products for each
        if len(variants) > 1:
            group_id = f"lidl_group_{p.get('id', '').replace('lidl-', '')}"

            for i, variant_name in enumerate(variants):
                # Clean up variant name (remove image description artifacts)
                clean_name = variant_name.strip()
                # Use shorter name if too long
                if len(clean_name) > 80:
                    clean_name = clean_name[:77] + '...'

                products.append({
                    **base_data,
                    'id': f"{p.get('id', '')}_v{i}",
                    'name': clean_name,
                    'offer_group_id': group_id,
                })
        else:
            # Single product or no variants - add as-is
            products.append({
                **base_data,
                'id': p.get('id', ''),  # Already has lidl- prefix from scraper
                'name': p.get('name', ''),
                'offer_group_id': None,
            })

    return products, data.get('folder_week', ''), folder_validity


def calculate_discount_percentage(offer_price, normal_price):
    """Calculate discount percentage."""
    if offer_price and normal_price and normal_price > offer_price:
        return round((1 - offer_price / normal_price) * 100)
    return None


def normalize_product_name(name):
    """Normalize product name for matching across supermarkets."""
    if not name:
        return ''
    # Lowercase and remove common variations
    normalized = name.lower().strip()
    # Remove brand prefixes that might differ
    for prefix in ['ah ', 'jumbo ', 'lidl ', '1 de beste ', 'g\'woon ']:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    # Remove common suffixes like pack sizes
    import re
    normalized = re.sub(r'\s*\d+\s*-?\s*pack\s*$', '', normalized)
    normalized = re.sub(r'\s*\d+\s*stuks?\s*$', '', normalized)
    return normalized.strip()


def extract_unit_count(name, package_desc=''):
    """Extract the number of units from product name or package description.

    Examples:
    - "Coca-Cola 8-pack" -> 8
    - "Fanta 12 stuks" -> 12
    - "6x330 ml" -> 6
    - "2 pakken" -> 2
    """
    import re
    text = f"{name} {package_desc}".lower()

    # Pattern: X-pack or X pack
    match = re.search(r'(\d+)\s*-?\s*pack', text)
    if match:
        return int(match.group(1))

    # Pattern: X stuks
    match = re.search(r'(\d+)\s*stuks?', text)
    if match:
        return int(match.group(1))

    # Pattern: Xx (like 6x330ml)
    match = re.search(r'(\d+)\s*x\s*\d+', text)
    if match:
        return int(match.group(1))

    # Pattern: X pakken/blikken/flesjes etc
    match = re.search(r'(\d+)\s*(?:pakken?|blikjes?|flesjes?|zakjes?|potjes?|dozen?|rollen?)', text)
    if match:
        return int(match.group(1))

    return 1  # Default to 1 unit


def extract_volume_liters(name, package_desc=''):
    """Extract total volume in liters from product name or package description.

    Examples:
    - "8 x 0,25 l" -> 2.0 (8 * 0.25)
    - "1.5 liter" -> 1.5
    - "2 liter" -> 2.0
    - "330 ml" -> 0.33
    - "6x330 ml" -> 1.98 (6 * 0.33)
    Returns None if no volume found (not a drink product)
    """
    import re
    text = f"{name} {package_desc}".lower().replace(',', '.')

    # Pattern: X x Y l (like "8 x 0.25 l")
    match = re.search(r'(\d+)\s*x\s*(\d+\.?\d*)\s*l(?:iter)?(?!\w)', text)
    if match:
        count = int(match.group(1))
        size = float(match.group(2))
        return round(count * size, 2)

    # Pattern: X x Y ml (like "6x330 ml")
    match = re.search(r'(\d+)\s*x\s*(\d+)\s*ml', text)
    if match:
        count = int(match.group(1))
        size_ml = int(match.group(2))
        return round(count * size_ml / 1000, 2)

    # Pattern: X liter or X l (single bottle like "1.5 liter" or "2 l")
    match = re.search(r'(\d+\.?\d*)\s*l(?:iter)?(?!\w)', text)
    if match:
        return float(match.group(1))

    # Pattern: X ml (single item like "330 ml")
    match = re.search(r'(\d+)\s*ml(?!\w)', text)
    if match:
        return round(int(match.group(1)) / 1000, 2)

    return None  # Not a drink or no volume info


def calculate_unit_price(offer_price, unit_count):
    """Calculate price per unit."""
    if offer_price and unit_count and unit_count > 0:
        return round(offer_price / unit_count, 2)
    return offer_price


def calculate_price_per_liter(offer_price, volume_liters):
    """Calculate price per liter for drinks."""
    if offer_price and volume_liters and volume_liters > 0:
        return round(offer_price / volume_liters, 2)
    return None


def extract_product_type(name, package_desc=''):
    """Extract product type keywords to distinguish similar products.

    Examples:
    - "Page vochtig toiletpapier" -> ['vochtig', 'toiletpapier']
    - "Page compleet schoon toiletpapier" -> ['toiletpapier']  (not 'vochtig')
    - "Coca-Cola Zero" -> ['zero']
    - "Coca-Cola Regular" -> ['regular']
    - "Coca-Cola 8x0.33L" -> ['blikjes'] (cans)
    - "Coca-Cola 2L" -> ['fles'] (bottle)
    """
    import re
    text = f"{name} {package_desc}".lower()

    # Extract key product type indicators
    type_keywords = []

    # Wet vs dry products
    if 'vochtig' in text or 'nat' in text or 'wet' in text:
        type_keywords.append('vochtig')

    # Sugar-free variants
    if 'zero' in text or 'sugar free' in text or 'suikervrij' in text:
        type_keywords.append('zero')
    if 'light' in text or 'diet' in text:
        type_keywords.append('light')

    # Flavor variants (important for drinks)
    flavors = ['original', 'regular', 'classic', 'orange', 'lemon', 'lime', 'cherry',
               'green', 'sparkling', 'still', 'naturel', 'bosvruchten', 'framboos',
               'aardbei', 'mango', 'perzik', 'citroen', 'sinaasappel']
    for flavor in flavors:
        if flavor in text:
            type_keywords.append(flavor)

    # Product form
    if 'rollen' in text or 'rol ' in text:
        type_keywords.append('rollen')
    if 'stuks' in text or 'stuk ' in text:
        type_keywords.append('stuks')

    # DRINK CONTAINER TYPES - Critical for soft drinks comparison
    # Cans (blikjes)
    if 'blik' in text or 'blikje' in text or 'can' in text:
        type_keywords.append('blikjes')
    # Multi-pack detection for cans: "8x0.33" or "8 x 330ml" patterns
    elif re.search(r'\d+\s*x\s*0?[.,]?33', text) or re.search(r'\d+\s*x\s*330\s*ml', text):
        type_keywords.append('blikjes')  # Standard 330ml = cans
    elif re.search(r'\d+\s*x\s*0?[.,]?25', text) or re.search(r'\d+\s*x\s*250\s*ml', text):
        type_keywords.append('blikjes')  # 250ml = small cans

    # Bottles (fles/flessen)
    if 'fles' in text or 'flessen' in text or 'bottle' in text:
        type_keywords.append('fles')
    # Large single bottles: "1.5 l", "2 liter", "1 l" (not multi-pack)
    # Only mark as 'fles' if it's NOT a multi-pack (no "X x" pattern)
    elif not re.search(r'\d+\s*x', text):
        # Check for single large bottle patterns
        if re.search(r'(1[.,]5|2)\s*l(?:iter)?(?!\w)', text):
            type_keywords.append('fles')

    # Multi-pack bottles (different from single bottles)
    if re.search(r'\d+\s*x\s*(?:1[.,]5|1|0[.,]5)\s*l', text):
        type_keywords.append('multipack_fles')

    # Dairy specifics
    if 'vla' in text:
        type_keywords.append('vla')
    if 'room' in text or 'slagroom' in text:
        type_keywords.append('room')
    if 'roomboter' in text or 'boter' in text:
        type_keywords.append('boter')
    if 'yoghurt' in text:
        type_keywords.append('yoghurt')
    if 'kwark' in text:
        type_keywords.append('kwark')
    if 'melk' in text and 'karnemelk' not in text:
        type_keywords.append('melk')
    if 'karnemelk' in text:
        type_keywords.append('karnemelk')

    # Food packaging types (canned vs carton vs fresh) - for food, not drinks
    if 'pak' in text or 'karton' in text:
        type_keywords.append('pak')

    # Meat products
    if 'knaks' in text or 'knakworst' in text:
        type_keywords.append('knakworst')
    if 'rookworst' in text:
        type_keywords.append('rookworst')

    return type_keywords


def products_are_same_type(p1, p2):
    """Check if two products are the same type (can be fairly compared).

    Returns True only if products are comparable (same product type).
    Critical for drinks: cans vs bottles vs multi-packs are NOT comparable.
    """
    name1 = (p1.get('name') or '').lower()
    name2 = (p2.get('name') or '').lower()
    pkg1 = (p1.get('package_description') or '').lower()
    pkg2 = (p2.get('package_description') or '').lower()

    type1 = set(extract_product_type(name1, pkg1))
    type2 = set(extract_product_type(name2, pkg2))

    # DRINK CONTAINER CHECK - These must match exactly for soft drinks
    drink_containers = {'blikjes', 'fles', 'multipack_fles'}
    containers1 = type1 & drink_containers
    containers2 = type2 & drink_containers

    # If either product has a container type, they must match EXACTLY
    # (A multi-pack and single bottle should not match even if both say "fles")
    if containers1 or containers2:
        # Special check: multipack vs single
        if ('multipack_fles' in containers1) != ('multipack_fles' in containers2):
            return False  # One is multipack, other is single = not comparable
        if ('blikjes' in containers1) != ('blikjes' in containers2):
            return False  # One is cans, other is not = not comparable
        # Check for exact match otherwise
        if containers1 != containers2:
            return False  # Different container types = not comparable

    # If either has type keywords, they must match
    if type1 and type2:
        # Must have at least one common type keyword
        common = type1 & type2
        # And must not have conflicting types
        conflicting_pairs = [
            ('vochtig', 'rollen'),  # wet wipes vs rolls
            ('zero', 'regular'), ('zero', 'original'),
            ('light', 'regular'), ('light', 'original'),
            ('vla', 'room'), ('vla', 'yoghurt'), ('room', 'yoghurt'),
            ('vla', 'kwark'), ('vla', 'boter'), ('vla', 'melk'),
            ('kwark', 'yoghurt'), ('kwark', 'boter'), ('kwark', 'melk'), ('kwark', 'room'),
            ('boter', 'yoghurt'), ('boter', 'melk'), ('boter', 'room'),
            ('melk', 'karnemelk'),
            ('blik', 'pak'),  # canned vs carton (for food)
            ('knakworst', 'rookworst'),  # different sausage types
            # Drink container conflicts
            ('blikjes', 'fles'), ('blikjes', 'multipack_fles'),
            ('fles', 'multipack_fles'),
        ]
        for a, b in conflicting_pairs:
            if (a in type1 and b in type2) or (b in type1 and a in type2):
                return False
        return bool(common) or (not type1 and not type2)

    # If one has 'vochtig' and other doesn't, they're different
    if 'vochtig' in type1 or 'vochtig' in type2:
        return 'vochtig' in type1 and 'vochtig' in type2

    # If one has 'zero'/'light' and other doesn't, check carefully
    sugar_free = {'zero', 'light'}
    if (type1 & sugar_free) != (type2 & sugar_free):
        return False

    # If one explicitly says 'blik' (canned) and other doesn't, they're different
    if 'blik' in type1 or 'blik' in type2:
        return 'blik' in type1 and 'blik' in type2

    # If one explicitly says 'pak' (carton) and other doesn't, they're different
    if 'pak' in type1 or 'pak' in type2:
        return 'pak' in type1 and 'pak' in type2

    return True


def find_price_comparisons(all_products):
    """Find products available at multiple supermarkets and compare prices PER UNIT or PER LITER.

    STRICT MATCHING: Only compares products that are truly the same:
    - Same brand
    - Same product type (e.g., don't compare wet wipes vs dry toilet paper)
    - Similar package sizes (within 50% of each other)
    """
    from difflib import SequenceMatcher

    # Calculate unit price and volume price for all products first
    for p in all_products:
        if p.get('offer_price'):
            # Calculate unit count and price
            unit_count = extract_unit_count(p.get('name', ''), p.get('package_description', ''))
            p['_unit_count'] = unit_count
            p['_unit_price'] = calculate_unit_price(p['offer_price'], unit_count)

            # Calculate volume and price per liter for drinks
            volume = extract_volume_liters(p.get('name', ''), p.get('package_description', ''))
            p['_volume_liters'] = volume
            if volume:
                p['_price_per_liter'] = calculate_price_per_liter(p['offer_price'], volume)
                # For drinks, use price per liter as the comparison metric
                p['_comparison_price'] = p['_price_per_liter']
                p['_comparison_unit'] = 'liter'
            else:
                p['_comparison_price'] = p['_unit_price']
                p['_comparison_unit'] = 'stuk'

    # Group products by brand for comparison
    brand_products = defaultdict(list)
    for p in all_products:
        if p.get('offer_price') and p.get('brand'):
            brand_products[p['brand'].lower()].append(p)

    comparisons = []
    seen_products = set()

    for brand, products in brand_products.items():
        if len(products) < 2:
            continue

        # Check if different supermarkets
        supermarkets = set(p['supermarket'] for p in products)
        if len(supermarkets) < 2:
            continue

        # Find truly comparable products using strict matching
        for i, p1 in enumerate(products):
            if p1['id'] in seen_products:
                continue

            comparable_products = [p1]

            for p2 in products[i+1:]:
                if p2['supermarket'] == p1['supermarket']:
                    continue
                if p2['id'] in seen_products:
                    continue

                # STRICT CHECK 1: Same product type
                if not products_are_same_type(p1, p2):
                    continue

                # STRICT CHECK 2: Same comparison unit (drinks vs non-drinks)
                if p1.get('_comparison_unit', 'stuk') != p2.get('_comparison_unit', 'stuk'):
                    continue

                # STRICT CHECK 3: Similar package sizes (within 50%)
                # For drinks, compare volumes
                if p1.get('_volume_liters') and p2.get('_volume_liters'):
                    vol_ratio = max(p1['_volume_liters'], p2['_volume_liters']) / min(p1['_volume_liters'], p2['_volume_liters'])
                    if vol_ratio > 1.5:  # More than 50% size difference
                        continue
                # For other products, compare unit counts
                elif p1.get('_unit_count', 1) > 1 or p2.get('_unit_count', 1) > 1:
                    count_ratio = max(p1.get('_unit_count', 1), p2.get('_unit_count', 1)) / max(1, min(p1.get('_unit_count', 1), p2.get('_unit_count', 1)))
                    if count_ratio > 2:  # More than 2x size difference for multi-packs
                        continue

                # STRICT CHECK 4: Name similarity (must be high)
                name1 = normalize_product_name(p1['name'])
                name2 = normalize_product_name(p2['name'])
                similarity = SequenceMatcher(None, name1, name2).ratio()

                if similarity >= 0.5:  # At least 50% name similarity
                    comparable_products.append(p2)

            if len(comparable_products) >= 2:
                # Check if different supermarkets
                sms = set(p['supermarket'] for p in comparable_products)
                if len(sms) < 2:
                    continue

                # Sort by comparison price (per liter or per unit)
                comparable_sorted = sorted(comparable_products, key=lambda x: x.get('_comparison_price', x['offer_price']))
                best = comparable_sorted[0]
                others = comparable_sorted[1:]

                if not others:
                    continue

                best_comparison_price = best.get('_comparison_price', best['offer_price'])
                max_comparison_price = max(p.get('_comparison_price', p['offer_price']) for p in others)
                savings_per_unit = max_comparison_price - best_comparison_price
                savings_pct = round((savings_per_unit / max_comparison_price) * 100) if max_comparison_price > 0 else 0

                if savings_pct >= 10 and best['id'] not in seen_products:  # At least 10% savings
                    seen_products.add(best['id'])
                    for o in others:
                        seen_products.add(o['id'])

                    comparison_unit = best.get('_comparison_unit', 'stuk')
                    comparisons.append({
                        'best_product': best,
                        'best_comparison_price': best_comparison_price,
                        'comparison_unit': comparison_unit,
                        'best_volume': best.get('_volume_liters'),
                        'best_unit_count': best.get('_unit_count', 1),
                        'other_prices': [{
                            'supermarket': p['supermarket'],
                            'price': p['offer_price'],
                            'comparison_price': p.get('_comparison_price', p['offer_price']),
                            'volume': p.get('_volume_liters'),
                            'unit_count': p.get('_unit_count', 1),
                            'name': p['name'],
                            'image_url': p.get('image_url', '')
                        } for p in others],
                        'savings_per_unit': round(savings_per_unit, 2),
                        'savings_pct': savings_pct,
                        'supermarket_count': len(sms)
                    })

    # Sort by savings percentage
    comparisons.sort(key=lambda x: x['savings_pct'], reverse=True)
    return comparisons[:20]


def generate_insights(all_products):
    """Generate insights from aggregated data."""
    insights = {
        'total_products': len(all_products),
        'by_supermarket': defaultdict(int),
        'with_prices': 0,
        'with_discounts': 0,
        'biggest_discounts': [],
        'price_comparisons': [],  # Products available at multiple supermarkets with best price
        'vegetarian_products': [],
        'biological_products': [],
        'with_nutriscore': defaultdict(int),
        'category_distribution': defaultdict(int),
        'lidl_plus_deals': 0,
        'average_discount_by_supermarket': {}
    }

    discount_totals = defaultdict(list)

    for p in all_products:
        sm = p['supermarket']
        insights['by_supermarket'][sm] += 1

        if p.get('offer_price'):
            insights['with_prices'] += 1

        if p.get('discount_text'):
            insights['with_discounts'] += 1

        if p.get('is_vegetarian'):
            insights['vegetarian_products'].append(p)

        if p.get('is_biological'):
            insights['biological_products'].append(p)

        if p.get('nutriscore'):
            insights['with_nutriscore'][p['nutriscore']] += 1

        if p.get('category'):
            # Normalize category - take first part
            cat = p['category'].split('/')[0].strip()
            if cat:
                insights['category_distribution'][cat] += 1

        if p.get('requires_card'):
            insights['lidl_plus_deals'] += 1

        # Calculate discount
        discount_pct = calculate_discount_percentage(p.get('offer_price'), p.get('normal_price'))
        if discount_pct:
            p['discount_percentage'] = discount_pct
            discount_totals[sm].append(discount_pct)

    # Calculate average discount by supermarket
    for sm, discounts in discount_totals.items():
        if discounts:
            insights['average_discount_by_supermarket'][sm] = round(sum(discounts) / len(discounts), 1)

    # Find biggest discounts (products with prices and calculated discount)
    products_with_discount = [p for p in all_products if p.get('discount_percentage')]
    products_with_discount.sort(key=lambda x: x['discount_percentage'], reverse=True)
    insights['biggest_discounts'] = products_with_discount[:20]

    # Find price comparisons - same products at different supermarkets
    insights['price_comparisons'] = find_price_comparisons(all_products)

    return insights


def aggregate_all():
    """Load and aggregate all supermarket data."""
    print("Aggregating supermarket data...")

    all_products = []
    weeks = {}
    folder_validity = {}

    # Load each supermarket
    loaders = [
        ('Dirk', load_dirk),
        ('Hoogvliet', load_hoogvliet),
        ('Albert Heijn', load_ah),
        ('Jumbo', load_jumbo),
        ('Lidl', load_lidl)
    ]

    for name, loader in loaders:
        try:
            products, week, validity = loader()
            all_products.extend(products)
            weeks[name] = week
            if validity:
                folder_validity[name] = validity
            print(f"  {name}: {len(products)} products, validity: {validity.get('start_date', 'N/A')} - {validity.get('end_date', 'N/A')}" if validity else f"  {name}: {len(products)} products")
        except Exception as e:
            print(f"  {name}: Error - {e}")

    print(f"\nTotal: {len(all_products)} products")

    # Generate insights
    print("\nGenerating insights...")
    insights = generate_insights(all_products)

    # Build output
    output = {
        'aggregated_at': datetime.now().isoformat(),
        'folder_weeks': weeks,
        'folder_validity': folder_validity,
        'total_products': len(all_products),
        'insights': {
            'total_products': insights['total_products'],
            'by_supermarket': dict(insights['by_supermarket']),
            'with_prices': insights['with_prices'],
            'with_discounts': insights['with_discounts'],
            'average_discount_by_supermarket': insights['average_discount_by_supermarket'],
            'category_distribution': dict(sorted(insights['category_distribution'].items(), key=lambda x: x[1], reverse=True)[:15]),
            'nutriscore_distribution': dict(insights['with_nutriscore']),
            'vegetarian_count': len(insights['vegetarian_products']),
            'biological_count': len(insights['biological_products']),
            'lidl_plus_deals': insights['lidl_plus_deals']
        },
        'highlights': {
            'biggest_discounts': [{
                'name': p['name'],
                'supermarket': p['supermarket'],
                'offer_price': p['offer_price'],
                'normal_price': p['normal_price'],
                'discount_percentage': p['discount_percentage'],
                'image_url': p['image_url']
            } for p in insights['biggest_discounts'][:10]],
            'price_comparisons': [{
                'name': c['best_product']['name'],
                'best_supermarket': c['best_product']['supermarket'],
                'best_price': c['best_product']['offer_price'],
                'best_unit_price': c.get('best_unit_price', c['best_product']['offer_price']),
                'best_unit_count': c.get('best_unit_count', 1),
                'other_prices': c['other_prices'],
                'savings_per_unit': c.get('savings_per_unit', 0),
                'savings_pct': c['savings_pct'],
                # Use best product image, or fallback to an image from other products
                'image_url': c['best_product']['image_url'] or next(
                    (o.get('image_url') for o in c['other_prices'] if o.get('image_url')), ''
                )
            } for c in insights['price_comparisons'][:10]]
        },
        'products': all_products
    }

    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {OUTPUT_FILE}")

    # Print insights summary
    print("\n=== INSIGHTS SUMMARY ===")
    print(f"Total products: {insights['total_products']}")
    print(f"Products with prices: {insights['with_prices']}")
    print(f"Products with discounts: {insights['with_discounts']}")
    print(f"\nBy supermarket:")
    for sm, count in sorted(insights['by_supermarket'].items(), key=lambda x: x[1], reverse=True):
        avg_disc = insights['average_discount_by_supermarket'].get(sm, 'N/A')
        print(f"  {sm}: {count} products (avg discount: {avg_disc}%)")

    if insights['biggest_discounts']:
        print(f"\nTop 5 biggest discounts:")
        for p in insights['biggest_discounts'][:5]:
            print(f"  {p['discount_percentage']}% off: {p['name']} @ {p['supermarket']} (€{p['offer_price']:.2f} was €{p['normal_price']:.2f})")

    # Archive to price history database
    print("\n=== ARCHIVING TO PRICE HISTORY ===")
    try:
        from price_tracker import PriceTracker
        tracker = PriceTracker()
        imported, skipped = tracker.import_from_aggregated(OUTPUT_FILE)
        print(f"Archived: {imported} new prices, {skipped} already in database")

        summary = tracker.get_summary()
        print(f"Database now has: {summary['total_records']} records across {summary['total_weeks']} weeks")
        tracker.close()
    except Exception as e:
        print(f"Warning: Could not archive to price history: {e}")

    return output


if __name__ == "__main__":
    aggregate_all()
