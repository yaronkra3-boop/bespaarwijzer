"""
Dirk Folder Extractor

Extracts all promotion data from Dirk's weekly folder.
Dirk embeds complete offer data in __NUXT_DATA__ JSON on their website.

Sources:
- Current week: https://www.dirk.nl/aanbiedingen
- Next week (vanaf woensdag): https://www.dirk.nl/aanbiedingen/vanaf-woensdag

The data has two levels:
- Offer level: General offer info (name, image, dates)
- Nested product level: Accurate product details (prices, brand, category, logos)

We extract from the nested product level for accuracy, with offer level as fallback.

Data extracted per product:
- name, brand, packaging, unit_size, weight (extracted from variant names)
- offer_price, normal_price (from nested product - most accurate)
- image URL (offer image, falls back to product image if missing)
- start_date, end_date
- category (department/webgroup)
- product variants (for multi-product offers)
- logos/badges (e.g., "1 de Beste", vegetarian, etc.)

Usage:
  python3 extract.py              # Fetches current week folder
  python3 extract.py --next-week  # Fetches next week (vanaf woensdag)
  python3 generate_html.py        # Generates folder.html from folder_data.json
"""

import json
import re
import requests
import sys
from datetime import datetime
from urllib.parse import quote

OUTPUT_FILE = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/dirk/folder_data.json"

# URLs for different folder periods
CURRENT_WEEK_URL = "https://www.dirk.nl/aanbiedingen"
NEXT_WEEK_URL = "https://www.dirk.nl/aanbiedingen/vanaf-woensdag"

# Regex pattern to extract weight/quantity from product names
# Matches patterns like: 500 gram, 1,5 liter, 750 ml, 6 stuks, etc.
WEIGHT_PATTERN = re.compile(
    r'(\d+(?:[,\.]\d+)?\s*(?:gram|gr|g|kilo|kg|liter|l|ml|cl|stuks|stuk|pak|pakken|blikjes|blik|flesjes|fles|zakjes|zak|potjes|pot|bakjes|bak|dozen|doos|rollen|rol))\b',
    re.IGNORECASE
)
IMAGE_BASE_URL = "https://web-fileserver.dirk.nl/offers/"
PRODUCT_IMAGE_BASE_URL = "https://web-fileserver.dirk.nl/"
LOGO_IMAGE_BASE_URL = "https://web-fileserver.dirk.nl/"


def extract_weight_from_text(text):
    """Extract weight/quantity from product name or variant text.

    Examples:
    - "1 de Beste Snoeptomaatjes 500 gram" -> "500 gram"
    - "Coca-Cola 6x330 ml" -> "330 ml"
    - "Melk 1,5 liter" -> "1,5 liter"
    """
    if not text:
        return None
    match = WEIGHT_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    return None


def slugify(text):
    """Convert text to URL-friendly slug."""
    if not text:
        return ''
    # Lowercase and replace spaces/special chars
    slug = text.lower().strip()
    # Replace accented characters
    slug = slug.replace('é', 'e').replace('è', 'e').replace('ë', 'e')
    slug = slug.replace('á', 'a').replace('à', 'a').replace('ä', 'a')
    slug = slug.replace('ö', 'o').replace('ó', 'o').replace('ò', 'o')
    slug = slug.replace('ü', 'u').replace('ú', 'u').replace('ù', 'u')
    slug = slug.replace('ï', 'i').replace('í', 'i').replace('ì', 'i')
    # Replace special quotes (curly apostrophe and regular apostrophe)
    slug = slug.replace('\u2019', '-').replace("'", '-')
    # Replace spaces and special chars with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def build_product_url(name, department, webgroup, product_id):
    """Build Dirk product URL from product details.

    URL pattern: https://www.dirk.nl/boodschappen/{department}/{webgroup}/{name-slug}/{product_id}
    """
    if not product_id:
        return ''

    # Slugify the components
    dept_slug = slugify(department) if department else ''
    webgroup_slug = slugify(webgroup) if webgroup else ''
    name_slug = slugify(name) if name else ''

    # Build URL - need at least product_id and name
    if dept_slug and webgroup_slug:
        return f"https://www.dirk.nl/boodschappen/{dept_slug}/{webgroup_slug}/{name_slug}/{product_id}"
    elif dept_slug:
        return f"https://www.dirk.nl/boodschappen/{dept_slug}/{name_slug}/{product_id}"
    else:
        # Fallback - just product ID (won't work but at least we have the ID)
        return ''


def extract_dirk_folder(next_week=False):
    """Extract all products from Dirk's weekly folder.

    Args:
        next_week: If True, fetch from /aanbiedingen/vanaf-woensdag (next week's offers)
                   If False, fetch from /aanbiedingen (current week)
    """
    url = NEXT_WEEK_URL if next_week else CURRENT_WEEK_URL
    period = "next week (vanaf woensdag)" if next_week else "current week"

    print(f"Fetching Dirk folder ({period}) from {url} ...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    html = response.text

    # Extract __NUXT_DATA__ JSON
    match = re.search(r'id="__NUXT_DATA__"[^>]*>(\[.+?\])</script>', html, re.DOTALL)
    if not match:
        print("Could not find NUXT data!")
        return None

    try:
        nuxt_data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"Failed to parse NUXT data: {e}")
        return None

    # Dereference function for NUXT's indexed data structure
    def deref(idx, depth=0):
        if depth > 10:  # Prevent infinite recursion
            return idx
        if isinstance(idx, int) and idx < len(nuxt_data):
            val = nuxt_data[idx]
            if isinstance(val, dict):
                return {k: deref(v, depth+1) for k, v in val.items()}
            elif isinstance(val, list):
                return [deref(item, depth+1) for item in val]
            return val
        return idx

    # Extract products
    products = []
    seen_ids = set()

    for i, item in enumerate(nuxt_data):
        if isinstance(item, dict) and 'offerId' in item:
            offer = deref(i)
            if isinstance(offer, dict) and offer.get('offerPrice'):
                offer_id = offer.get('offerId')

                # Skip duplicates
                if offer_id in seen_ids:
                    continue
                seen_ids.add(offer_id)

                # Build offer-level image URL (fallback)
                image_path = offer.get('image', '')
                offer_image_url = f"{IMAGE_BASE_URL}{image_path}" if image_path else ''

                # Extract from nested products array (primary source - most accurate)
                nested_products = offer.get('products', [])

                # Initialize with offer-level data as defaults
                best_offer_price = offer.get('offerPrice')
                best_normal_price = offer.get('normalPrice')
                department = ''
                webgroup = ''
                brand = ''
                unit_size = ''
                weight = ''  # Actual weight extracted from variant names
                product_variants = []
                product_images = []
                logos = []
                nested_product_id = None  # Product ID for building URL

                # Process each nested product for accurate data
                for np in nested_products:
                    if np and isinstance(np, dict):
                        # Get prices from nested product (more accurate than offer level)
                        np_offer_price = np.get('offerPrice')
                        np_normal_price = np.get('normalPrice')

                        # Use first nested product's prices (they're the accurate ones)
                        if np_offer_price is not None and best_offer_price == offer.get('offerPrice'):
                            best_offer_price = np_offer_price
                        if np_normal_price is not None and best_normal_price == offer.get('normalPrice'):
                            best_normal_price = np_normal_price

                        # Extract productInformation (contains most detailed data)
                        prod_info = np.get('productInformation', {})
                        if prod_info and isinstance(prod_info, dict):
                            # Get product ID for URL (use first one found)
                            if nested_product_id is None:
                                nested_product_id = prod_info.get('productId')

                            # Category info
                            if not department:
                                department = prod_info.get('department', '')
                            if not webgroup:
                                webgroup = prod_info.get('webgroup', '')

                            # Brand
                            if not brand:
                                brand = prod_info.get('brand', '')

                            # Unit size / packaging from product level (more specific)
                            nested_packaging = prod_info.get('packaging', '')
                            if nested_packaging and not unit_size:
                                unit_size = nested_packaging

                            # Collect variant names (full product names)
                            variant_name = prod_info.get('headerText', '')
                            if variant_name:
                                product_variants.append(variant_name)
                                # Extract weight from variant name if not already found
                                if not weight:
                                    extracted_weight = extract_weight_from_text(variant_name)
                                    if extracted_weight:
                                        weight = extracted_weight

                            # Collect product images
                            prod_image = prod_info.get('image', '')
                            if prod_image:
                                full_image_url = f"{PRODUCT_IMAGE_BASE_URL}{prod_image}"
                                if full_image_url not in product_images:
                                    product_images.append(full_image_url)

                            # Collect logos/badges
                            for logo in prod_info.get('logos', []):
                                if logo and isinstance(logo, dict):
                                    logo_desc = logo.get('description', '').strip()
                                    logo_image = logo.get('image', '')
                                    logo_link = logo.get('link', '')
                                    if logo_desc and logo_desc not in [l.get('name') for l in logos]:
                                        logos.append({
                                            'name': logo_desc,
                                            'image_url': f"{LOGO_IMAGE_BASE_URL}{logo_image}" if logo_image else '',
                                            'link': logo_link
                                        })

                # Build category string
                category = f"{department}/{webgroup}" if department and webgroup else department or webgroup

                # Use best available image: offer image first, then first product image as fallback
                main_image_url = offer_image_url
                if not main_image_url and product_images:
                    main_image_url = product_images[0]

                # Build product URL using nested product ID
                product_url = build_product_url(
                    offer.get('headerText', ''),
                    department,
                    webgroup,
                    nested_product_id
                )

                product = {
                    'id': offer_id,
                    'product_id': nested_product_id,  # For reference
                    'name': offer.get('headerText', ''),
                    'brand': brand,
                    'packaging': offer.get('packaging', ''),
                    'unit_size': unit_size,
                    'weight': weight,  # Actual weight extracted from variant names (e.g., "500 gram")
                    'offer_price': best_offer_price,
                    'normal_price': best_normal_price,
                    'discount_text': offer.get('textPriceSign', '').strip(),
                    'image_url': main_image_url,
                    'product_images': product_images,
                    'product_url': product_url,
                    'start_date': offer.get('startDate'),
                    'end_date': offer.get('endDate'),
                    'category': category,
                    'department': department,
                    'webgroup': webgroup,
                    'variants': product_variants if len(product_variants) > 1 else [],
                    'logos': logos,
                }
                products.append(product)

    # Determine folder week from dates
    folder_week = None
    if products and products[0].get('start_date'):
        try:
            start = datetime.fromisoformat(products[0]['start_date'].replace('Z', '+00:00'))
            folder_week = f"week-{start.isocalendar()[1]}-{start.year}"
        except:
            pass

    # Data validation - minimum product count check
    MIN_PRODUCTS = 80  # Dirk typically has 100-150 products
    if len(products) < MIN_PRODUCTS:
        raise ValueError(f"VALIDATION FAILED: Dirk returned only {len(products)} products (minimum: {MIN_PRODUCTS}). Website may have changed.")

    # Build output
    output = {
        'supermarket': 'Dirk',
        'folder_week': folder_week,
        'extracted_at': datetime.now().isoformat(),
        'source_url': url,
        'product_count': len(products),
        'products': products
    }

    # Save current file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Archive copy with week number
    import os
    week_num = datetime.now().isocalendar()[1]
    archive_dir = os.path.dirname(OUTPUT_FILE) + '/archive'
    os.makedirs(archive_dir, exist_ok=True)
    archive_file = f"{archive_dir}/folder_data_week_{week_num}_dirk.json"
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Archived to: {archive_file}")

    # Print summary
    with_brand = sum(1 for p in products if p.get('brand'))
    with_category = sum(1 for p in products if p.get('category'))
    with_unit_size = sum(1 for p in products if p.get('unit_size'))
    with_weight = sum(1 for p in products if p.get('weight'))
    with_logos = sum(1 for p in products if p.get('logos'))
    with_variants = sum(1 for p in products if p.get('variants'))
    with_url = sum(1 for p in products if p.get('product_url'))

    print(f"\nExtracted {len(products)} products from Dirk folder")
    print(f"  - With brand: {with_brand}")
    print(f"  - With category: {with_category}")
    print(f"  - With unit_size: {with_unit_size}")
    print(f"  - With weight: {with_weight}")
    print(f"  - With logos: {with_logos}")
    print(f"  - With variants: {with_variants}")
    print(f"  - With product URL: {with_url}")
    print(f"\nSaved to: {OUTPUT_FILE}")

    return output


if __name__ == "__main__":
    # Check for --next-week flag
    next_week = '--next-week' in sys.argv or '-n' in sys.argv
    extract_dirk_folder(next_week=next_week)
