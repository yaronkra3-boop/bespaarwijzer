"""
Jumbo Supermarket Promotions Extractor (v2)

Extracts all weekly promotions from the Jumbo website with FULL product data.
Uses NUXT_DATA JSON embedded in promotion pages for accurate prices, brands, and categories.

Sources:
- Current week: https://www.jumbo.com/aanbiedingen/nu
- Next week: Available via /acties/weekaanbiedingen (check for next week folder slug)

Data extracted per product:
- id, name, brand, category
- offer_price, normal_price, price_per_unit
- unit_size, image_url
- promo_tag (discount type), validity

Usage:
  python3 extract.py              # Fetches current week
  python3 extract.py --next-week  # Fetches next week folder
"""

import requests
import json
import re
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
OFFERS_URL = "https://www.jumbo.com/aanbiedingen/nu"
WEEKAANBIEDINGEN_URL = "https://www.jumbo.com/acties/weekaanbiedingen"
OUTPUT_FILE = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/jumbo/folder_data.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"
}


def fetch_offers_page():
    """Fetch the main offers page HTML."""
    print("Fetching main offers page...")
    response = requests.get(OFFERS_URL, headers=HEADERS)
    response.raise_for_status()
    return response.text


def get_next_week_folder_slug():
    """
    Get the next week's Publitas folder slug from weekaanbiedingen page.
    Returns tuple of (current_week_slug, next_week_slug).
    """
    print("Fetching weekaanbiedingen page to find folder slugs...")
    response = requests.get(WEEKAANBIEDINGEN_URL, headers=HEADERS)
    response.raise_for_status()
    html = response.text

    # Find folder slugs like: jumbo-actiefolder-xxxx-50, jumbo-actiefolder-xxxx-51
    # The slugs appear directly in the HTML
    folder_pattern = r'jumbo-actiefolder-[a-z]+-(\d+)'
    matches = re.findall(folder_pattern, html)

    if not matches:
        print("No folder slugs found")
        return None, None

    # Get unique slugs with their week numbers
    seen = set()
    folders = []
    for match in re.finditer(r'(jumbo-actiefolder-[a-z]+-(\d+))', html):
        slug = match.group(1)
        week = int(match.group(2))
        if slug not in seen:
            seen.add(slug)
            folders.append((slug, week))

    # Sort by week number
    folders.sort(key=lambda x: x[1])
    print(f"  Found folder slugs: {[f[0] for f in folders]}")

    if len(folders) >= 2:
        return folders[0][0], folders[1][0]
    elif len(folders) == 1:
        return folders[0][0], None

    return None, None


def extract_products_from_publitas_folder(folder_slug):
    """
    Extract products from a Jumbo Publitas folder using hotspots.
    Returns list of promotion URLs found in the folder.
    """
    print(f"Extracting from Publitas folder: {folder_slug}")

    # Get folder data
    data_url = f"https://view.publitas.com/jumbo-supermarkten/{folder_slug}/data.json"
    response = requests.get(data_url, headers=HEADERS)
    response.raise_for_status()
    folder_data = response.json()

    total_pages = len(folder_data.get('spreads', []))
    print(f"  Folder has {total_pages} pages")

    # Extract promotion URLs from hotspots
    promo_urls = set()

    for page_num in range(1, total_pages * 2 + 1):  # Each spread has 2 pages
        hotspots_url = f"https://view.publitas.com/jumbo-supermarkten/{folder_slug}/page/{page_num}/hotspots_data.json"
        try:
            resp = requests.get(hotspots_url, timeout=10)
            if resp.status_code == 200:
                hotspots = resp.json()
                for h in hotspots:
                    if h.get('type') == 'externalLink' and h.get('url'):
                        url = h['url']
                        # Look for promotion URLs
                        if '/aanbiedingen/' in url and re.search(r'/\d+$', url):
                            promo_urls.add(url)
        except:
            pass

    print(f"  Found {len(promo_urls)} promotion links in folder")
    return list(promo_urls)


def extract_promotion_urls_from_main_page(html):
    """Extract all promotion URLs from the main offers page."""
    # Pattern: Extract promotion IDs and titles
    promo_pattern = r'"(301\d{4})","([^"]+)","([^"]+)","([^"]*)"'
    promo_matches = re.findall(promo_pattern, html)

    # Pattern: Extract promotion URLs
    url_pattern = r'"/aanbiedingen/([^"]+/\d+)"'
    urls = re.findall(url_pattern, html)
    url_map = {}
    for url in urls:
        parts = url.split('/')
        if len(parts) >= 2:
            promo_id = parts[-1]
            url_map[promo_id] = f"https://www.jumbo.com/aanbiedingen/{url}"

    # Build promotion list with URLs
    promotions = []
    seen_ids = set()
    for pid, uuid, title, subtitle in promo_matches:
        if pid in seen_ids:
            continue
        seen_ids.add(pid)

        promotions.append({
            "promo_id": pid,
            "promo_title": title.replace('\\u003Cbr />', ' ').replace('\\u003Cbr>', ' ').replace('&amp;', '&'),
            "promo_subtitle": subtitle.replace('\\u003Cbr />', ' ').replace('&amp;', '&') if subtitle else None,
            "url": url_map.get(pid, f"https://www.jumbo.com/aanbiedingen/{pid}"),
        })

    print(f"Found {len(promotions)} promotion groups")
    return promotions


def extract_products_from_promo_page(url):
    """
    Extract complete product data from a Jumbo promotion page using NUXT_DATA.

    Returns list of products with: id, name, brand, category, prices, unit_size, image_url
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        html = response.text

        # Find NUXT_DATA JSON
        match = re.search(r'id="__NUXT_DATA__"[^>]*>(\[.+?\])</script>', html, re.DOTALL)
        if not match:
            return [], None, None

        nuxt_data = json.loads(match.group(1))

        # Find type string indices
        type_indices = {}
        for i, item in enumerate(nuxt_data):
            if item in ['Product', 'Price', 'PricePerUnit', 'PromotionTag', 'Promotion', 'PromotionDurationTexts']:
                type_indices[item] = i

        # Dereference function for NUXT's indexed structure
        def deref(idx, depth=0):
            if depth > 15:
                return idx
            if isinstance(idx, int) and 0 <= idx < len(nuxt_data):
                val = nuxt_data[idx]
                if isinstance(val, dict):
                    return {k: deref(v, depth+1) for k, v in val.items()}
                elif isinstance(val, list):
                    return [deref(item, depth+1) for item in val]
                return val
            return idx

        # Extract products, promo tag, and duration info
        products = []
        promo_tag = None
        promo_title = None
        validity = None
        promo_image = None

        product_type_idx = type_indices.get('Product')
        promo_tag_type_idx = type_indices.get('PromotionTag')
        promo_type_idx = type_indices.get('Promotion')
        duration_type_idx = type_indices.get('PromotionDurationTexts')

        for i, item in enumerate(nuxt_data):
            if isinstance(item, dict):
                typename_ref = item.get('__typename')

                if typename_ref == product_type_idx:
                    product = deref(i)
                    products.append(product)

                elif typename_ref == promo_tag_type_idx and not promo_tag:
                    tag = deref(i)
                    promo_tag = tag.get('text')

                elif typename_ref == promo_type_idx and not promo_title:
                    promo = deref(i)
                    promo_title = promo.get('title')
                    promo_image = promo.get('image')

                elif typename_ref == duration_type_idx and not validity:
                    duration = deref(i)
                    validity = duration.get('shortTitle')

        return products, {
            'promo_tag': promo_tag,
            'promo_title': promo_title,
            'promo_image': promo_image,
            'validity': validity
        }, None

    except Exception as e:
        return [], None, str(e)


def transform_product(raw_product, promo_info, promo_url):
    """Transform raw NUXT product data to standardized format."""
    prices = raw_product.get('prices', {})
    if not isinstance(prices, dict):
        prices = {}

    price_per_unit = prices.get('pricePerUnit', {})
    if not isinstance(price_per_unit, dict):
        price_per_unit = {}

    # Convert prices from cents to euros
    normal_price = prices.get('price')
    promo_price = prices.get('promoPrice')
    ppu_price = price_per_unit.get('price')

    return {
        'id': raw_product.get('id', ''),
        'name': raw_product.get('title', ''),
        'brand': raw_product.get('brand', ''),
        'category': raw_product.get('category', ''),
        'unit_size': raw_product.get('subtitle', ''),
        'offer_price': promo_price / 100 if promo_price else (normal_price / 100 if normal_price else None),
        'normal_price': normal_price / 100 if normal_price else None,
        'price_per_unit': ppu_price / 100 if ppu_price else None,
        'price_unit': price_per_unit.get('unit', ''),
        'discount_tag': promo_info.get('promo_tag') if promo_info else None,
        'promo_title': promo_info.get('promo_title') if promo_info else None,
        'validity': promo_info.get('validity') if promo_info else None,
        'image_url': raw_product.get('image', ''),
        'source_url': promo_url,
    }


def main(next_week=False):
    print("=" * 60)
    print("Jumbo Promotions Extractor v2 (NUXT_DATA)")
    print("=" * 60)

    source_url = OFFERS_URL
    folder_week = None

    if next_week:
        # Get next week folder from weekaanbiedingen page
        current_slug, next_slug = get_next_week_folder_slug()

        if not next_slug:
            print("\nNo next week folder found! Falling back to current week.")
            html = fetch_offers_page()
            promotions = extract_promotion_urls_from_main_page(html)
        else:
            print(f"\nUsing next week folder: {next_slug}")
            # Extract week number from slug (e.g., jumbo-actiefolder-dtcy-51 -> 51)
            week_match = re.search(r'-(\d+)$', next_slug)
            if week_match:
                week_num = int(week_match.group(1))
                folder_week = f"week-{week_num}-{datetime.now().year}"

            # Get promotion URLs from the Publitas folder
            promo_urls = extract_products_from_publitas_folder(next_slug)

            if not promo_urls:
                print(f"\n⚠️  Next week folder ({next_slug}) has no promotion links yet.")
                print("   The folder is available as a preview but hotspots haven't been added.")
                print("   Falling back to current week data...\n")
                html = fetch_offers_page()
                promotions = extract_promotion_urls_from_main_page(html)
                folder_week = None  # Reset to let it calculate current week
            else:
                # Convert to promotions format
                promotions = []
                for url in promo_urls:
                    # Extract promo ID from URL
                    match = re.search(r'/(\d+)$', url)
                    if match:
                        promo_id = match.group(1)
                        promotions.append({
                            'promo_id': promo_id,
                            'promo_title': f"Promo {promo_id}",
                            'promo_subtitle': None,
                            'url': url if url.startswith('http') else f"https://www.jumbo.com{url}",
                        })

                source_url = f"https://view.publitas.com/jumbo-supermarkten/{next_slug}/"
    else:
        # Fetch main offers page and extract promotion URLs
        html = fetch_offers_page()
        promotions = extract_promotion_urls_from_main_page(html)

    if not promotions:
        print("\nNo promotions found!")
        return

    # Extract products from each promotion page in parallel
    print(f"\nExtracting products from {len(promotions)} promotion pages...")
    all_products = []
    promo_summaries = []
    errors = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(extract_products_from_promo_page, p['url']): p
            for p in promotions
        }

        for i, future in enumerate(as_completed(futures)):
            promo = futures[future]
            products, promo_info, error = future.result()

            if error:
                errors.append(f"{promo['promo_title']}: {error}")

            # Transform and add products
            for raw_product in products:
                product = transform_product(raw_product, promo_info, promo['url'])
                all_products.append(product)

            # Track promotion summary
            promo_summaries.append({
                'promo_id': promo['promo_id'],
                'title': promo['promo_title'],
                'product_count': len(products),
                'discount_tag': promo_info.get('promo_tag') if promo_info else None,
                'validity': promo_info.get('validity') if promo_info else None,
            })

            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(promotions)} promotions ({len(all_products)} products)...")

    # Remove duplicate products (same product might appear in multiple promos)
    seen_ids = set()
    unique_products = []
    for p in all_products:
        if p['id'] and p['id'] not in seen_ids:
            seen_ids.add(p['id'])
            unique_products.append(p)

    print(f"\nExtracted {len(unique_products)} unique products from {len(promotions)} promotions")

    # Data validation - minimum product count check
    MIN_PRODUCTS = 150  # Jumbo typically has 300-500 products
    if len(unique_products) < MIN_PRODUCTS:
        raise ValueError(f"VALIDATION FAILED: Jumbo returned only {len(unique_products)} products (minimum: {MIN_PRODUCTS}). Website may have changed.")

    # Build output
    now = datetime.now()
    if not folder_week:
        week_num = now.isocalendar()[1]
        folder_week = f"week-{week_num}-{now.year}"

    output = {
        "supermarket": "Jumbo",
        "folder_week": folder_week,
        "extracted_at": now.isoformat(),
        "source_url": source_url,
        "product_count": len(unique_products),
        "promotion_count": len(promotions),
        "products": unique_products,
    }

    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Archive copy with week number
    import os
    week_num = now.isocalendar()[1]
    archive_dir = os.path.dirname(OUTPUT_FILE) + '/archive'
    os.makedirs(archive_dir, exist_ok=True)
    archive_file = f"{archive_dir}/folder_data_week_{week_num}_jumbo.json"
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Archived to: {archive_file}")

    # Print summary
    print(f"\n{'=' * 60}")
    print("Extraction complete!")
    print(f"{'=' * 60}")
    print(f"Total unique products: {len(unique_products)}")
    print(f"With brand: {sum(1 for p in unique_products if p.get('brand'))}")
    print(f"With category: {sum(1 for p in unique_products if p.get('category'))}")
    print(f"With offer_price: {sum(1 for p in unique_products if p.get('offer_price'))}")
    print(f"With normal_price: {sum(1 for p in unique_products if p.get('normal_price'))}")
    print(f"With price_per_unit: {sum(1 for p in unique_products if p.get('price_per_unit'))}")
    print(f"With images: {sum(1 for p in unique_products if p.get('image_url'))}")
    print(f"Output saved to: {OUTPUT_FILE}")

    if errors:
        print(f"\nWarnings ({len(errors)}):")
        for e in errors[:5]:
            print(f"  - {e}")

    # Show sample products
    print(f"\nSample products:")
    for p in unique_products[:5]:
        price_str = f"€{p['offer_price']:.2f}" if p.get('offer_price') else "N/A"
        normal_str = f" (was €{p['normal_price']:.2f})" if p.get('normal_price') and p.get('offer_price') != p.get('normal_price') else ""
        print(f"  {p['name'][:45]:45} | {p.get('brand', 'N/A'):15} | {price_str}{normal_str}")

    return output


if __name__ == "__main__":
    # Check for --next-week flag
    next_week = '--next-week' in sys.argv or '-n' in sys.argv
    main(next_week=next_week)
