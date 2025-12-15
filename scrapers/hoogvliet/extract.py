"""
Hoogvliet Folder Extractor

Extracts all promotion data from Hoogvliet's weekly folder.
Hoogvliet uses Publitas for their digital folder at folder.hoogvliet.com.

Data extracted per product:
- name, brand
- package_description (e.g., "Schaal van 300 gram", "2 pakken van 150 gram")
- offer_price, normal_price
- unit (per stuk, per fles, per kilo, etc.)
- discount_text (korting percentage or deal type)
- image URL
- category
- freshDays, isVegetarian, isBiological, etc.
"""

import json
import re
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_FILE = "/Users/yaronkra/Jarvis/bespaarwijzer/scrapers/hoogvliet/folder_data.json"
FOLDER_BASE_URL = "https://folder.hoogvliet.com"
OFFER_IMAGE_BASE = "https://www.hoogvliet.com/INTERSHOP/static/WFS/org-webshop-Site/-/org/nl_NL/ACT"


def get_current_folder_slug():
    """Get the current Hoogvliet folder slug by following redirect."""
    response = requests.get(f"{FOLDER_BASE_URL}/", allow_redirects=True, timeout=30)
    # URL will be like https://folder.hoogvliet.com/folder_2025_50/page/1
    match = re.search(r'folder\.hoogvliet\.com/([^/]+)/', response.url)
    if match:
        return match.group(1)
    return None


def get_folder_info(slug):
    """Get folder metadata including number of pages."""
    data_url = f"{FOLDER_BASE_URL}/{slug}/data.json"
    response = requests.get(data_url, timeout=30)
    data = response.json()

    # New Publitas API uses numPages directly instead of spreads
    total_pages = data.get('numPages', 0)

    # Fallback to old spreads format if present
    if total_pages == 0:
        spreads = data.get('spreads', [])
        total_pages = sum(len(s.get('pages', [])) for s in spreads)

    return {
        'spreads': (total_pages + 1) // 2,  # Approximate number of spreads
        'total_pages': total_pages,
        'data': data
    }


def get_all_hotspot_urls(slug, total_pages):
    """Get all product URLs from all pages of a folder."""
    hotspot_urls = set()

    # First page is single, rest are double spreads
    page_patterns = ['1']
    for i in range(2, total_pages + 1, 2):
        page_patterns.append(f"{i}-{i+1}")

    print(f"Fetching hotspots from {len(page_patterns)} page patterns...")

    for pattern in page_patterns:
        try:
            url = f"{FOLDER_BASE_URL}/{slug}/page/{pattern}/hotspots_data.json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                hotspots = response.json()
                for h in hotspots:
                    if h.get('type') == 'externalLink' and h.get('url'):
                        if '/aanbiedingen/' in h['url']:
                            hotspot_urls.add(h['url'])
        except Exception as e:
            pass

    return list(hotspot_urls)


def extract_grouped_products(html, offer_id, offer_info):
    """
    Extract all individual products from a grouped offer page.
    Some offers contain multiple products (e.g., "All Stoney Creek wines" with 8 variants).

    Returns a list of individual product dicts.
    """
    products = []

    # Decode HTML entities for easier parsing
    html_decoded = html.replace('&#47;', '/')

    # Find all product links with names in the product list
    # Pattern: <a class="product-title" href="URL"><h3>Name</h3></a>
    product_links = re.findall(
        r'<a class="product-title"[^>]*href="([^"]+)"[^>]*>\s*<h3>([^<]+)</h3>',
        html_decoded
    )

    # Find all product images from cdn.hoogvliet.com
    product_images = re.findall(
        r'src="(https://cdn\.hoogvliet\.com/Images/Product/L/[^"]+)"',
        html_decoded
    )

    # Find all data-track-click entries for individual products
    track_entries = re.findall(
        r"data-track-click='\{([^']+)\}'",
        html
    )

    # Parse track entries to get brand/category info
    product_details = []
    for entry in track_entries:
        try:
            data = json.loads('{' + entry + '}')
            if 'products' in data and data['products']:
                prod = data['products'][0]
                product_details.append({
                    'name': prod.get('name', ''),
                    'brand': prod.get('brand', ''),
                    'category': prod.get('category', '').replace('&#47;', '/'),
                    'price': prod.get('price'),
                    'fresh_days': int(prod.get('freshDays', 0)) if prod.get('freshDays') else None,
                    'is_vegetarian': prod.get('isVegetarion') == '1',
                    'is_biological': prod.get('isBiological') == '1',
                })
        except json.JSONDecodeError:
            pass

    # Match products with their images and details
    # Products and images appear in the same order in the HTML
    for i, (product_url, product_name) in enumerate(product_links):
        # Decode HTML entities in name
        product_name = product_name.replace('&amp;', '&').replace('&eacute;', 'é').replace('&euml;', 'ë')

        # Get matching image
        image_url = product_images[i] if i < len(product_images) else None

        # Try to find matching details by name
        details = None
        for d in product_details:
            if d['name'].lower() in product_name.lower() or product_name.lower() in d['name'].lower():
                details = d
                break

        # If no match found, use the details at the same index
        if not details and i < len(product_details):
            details = product_details[i]

        # Extract product ID from URL if possible
        pid_match = re.search(r'/product/([^;?]+)', product_url)
        product_slug = pid_match.group(1) if pid_match else None

        # Create unique ID for this variant
        variant_id = f"{offer_id}_{i+1}" if offer_id else f"hv_{product_slug}"

        product = {
            'id': variant_id,
            'name': product_name.strip(),
            'brand': details.get('brand', offer_info.get('brand', '')) if details else offer_info.get('brand', ''),
            'package_description': offer_info.get('package_description'),
            'offer_price': offer_info.get('offer_price'),
            'normal_price': offer_info.get('normal_price'),
            'unit': offer_info.get('unit'),
            'discount_text': offer_info.get('discount_text'),
            'category': details.get('category', offer_info.get('category', '')) if details else offer_info.get('category', ''),
            'image_url': image_url,
            'source_url': product_url if product_url.startswith('http') else f"https://www.hoogvliet.com{product_url.split(';')[0]}",
            'fresh_days': details.get('fresh_days') if details else offer_info.get('fresh_days'),
            'is_vegetarian': details.get('is_vegetarian', False) if details else offer_info.get('is_vegetarian', False),
            'is_biological': details.get('is_biological', False) if details else offer_info.get('is_biological', False),
            'is_new': offer_info.get('is_new', False),
            'is_lowest_price': offer_info.get('is_lowest_price', False),
            'offer_group_id': offer_id,  # Link back to parent offer
        }
        products.append(product)

    return products


def extract_product_data(url):
    """
    Extract product data from a Hoogvliet offer page.
    Now returns a LIST of products to handle grouped offers.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text

        # Extract offer ID from URL
        offer_id_match = re.search(r'/aanbiedingen/(\d+)', url)
        offer_id = offer_id_match.group(1) if offer_id_match else None

        # First, extract common offer info (prices, discount, etc.)
        offer_price = None
        normal_price = None

        # Look for price patterns
        price_match = re.search(r'<span class="price-euros[^"]*"[^>]*><span[^>]*>(\d+)</span><span class="price-seperator[^"]*">\.</span></span>\s*<span class="price-cents[^"]*"><sup>(\d+)</sup>', html)
        if price_match:
            offer_price = float(f"{price_match.group(1)}.{price_match.group(2)}")

        # Look for strikethrough price (normal price)
        # Format 1: <div class="strikethrough"><div>11.25</div></div>
        strike_match = re.search(r'class="strikethrough"[^>]*>\s*<div>(\d+\.?\d*)</div>', html, re.DOTALL)
        if strike_match:
            normal_price = float(strike_match.group(1))
        else:
            # Format 2: strikethrough with split euros/cents
            strike_match = re.search(r'strikethrough[^>]*>.*?<span[^>]*>(\d+)</span>.*?<sup>(\d+)</sup>', html, re.DOTALL)
            if strike_match:
                normal_price = float(f"{strike_match.group(1)}.{strike_match.group(2)}")

        # Extract unit info from promotion-short-title
        unit = None
        promo_title_match = re.search(r'promotion-short-title[^>]*>(.*?)</div>', html, re.DOTALL)
        if promo_title_match:
            promo_text = re.sub(r'<[^>]+>', '', promo_title_match.group(1)).strip()
            unit_match = re.search(r'(per\s+\w+)', promo_text, re.IGNORECASE)
            if unit_match:
                unit = unit_match.group(1)

        # Extract package description from div after h1
        package_description = None
        package_match = re.search(r'<h1>[^<]*</h1>\s*<div>([^<]+)</div>', html, re.DOTALL)
        if package_match:
            package_description = package_match.group(1).strip()

        # Extract discount text
        discount_text = None
        discount_match = re.search(r'(\d+)%\s*korting', html, re.IGNORECASE)
        if discount_match:
            discount_text = f"{discount_match.group(1)}% korting"
        else:
            deal_match = re.search(r'(\d+\s*(?:voor|halen|\+)\s*\d*[^<]{0,20})', html, re.IGNORECASE)
            if deal_match:
                discount_text = deal_match.group(1).strip()

        # Get main product info from first data-track-click
        main_brand = ''
        main_category = ''
        fresh_days = None
        is_vegetarian = False
        is_biological = False
        is_new = False
        is_lowest_price = False
        main_name = ''

        track_match = re.search(r'data-track-click=\'\{([^\']+)\}\'', html, re.DOTALL)
        if track_match:
            try:
                track_data = json.loads('{' + track_match.group(1) + '}')
                products = track_data.get('products', [])
                if products:
                    prod = products[0]
                    main_name = prod.get('name', '').strip()
                    main_brand = prod.get('brand', '')
                    main_category = prod.get('category', '').replace('&#47;', '/')
                    fresh_days = int(prod.get('freshDays', 0)) if prod.get('freshDays') else None
                    is_vegetarian = prod.get('isVegetarion') == '1'
                    is_biological = prod.get('isBiological') == '1'
                    is_new = prod.get('isNew') == '1'
                    is_lowest_price = prod.get('isLowestPrice') == '1'

                    # Also get price from track data if not found in HTML
                    if not offer_price and prod.get('price'):
                        offer_price = float(prod.get('price', 0))
            except json.JSONDecodeError:
                pass

        # Build offer_info dict with common data
        offer_info = {
            'offer_price': offer_price,
            'normal_price': normal_price,
            'unit': unit,
            'package_description': package_description,
            'discount_text': discount_text,
            'brand': main_brand,
            'category': main_category,
            'fresh_days': fresh_days,
            'is_vegetarian': is_vegetarian,
            'is_biological': is_biological,
            'is_new': is_new,
            'is_lowest_price': is_lowest_price,
        }

        # Check if this offer has multiple products in a product list
        # Look for product-list-container with multiple product-title links
        product_links = re.findall(
            r'<a class="product-title"[^>]*href="([^"]+)"[^>]*>\s*<h3>([^<]+)</h3>',
            html.replace('&#47;', '/')
        )

        if len(product_links) > 1:
            # This is a grouped offer - extract all individual products
            grouped_products = extract_grouped_products(html, offer_id, offer_info)
            if grouped_products:
                return grouped_products

        # Single product offer - return as before (but as a list)
        # Extract image URL
        image_url = None
        if offer_id:
            img_match = re.search(rf'src="([^"]*{offer_id}[^"]*\.jpg)"', html.replace('&#47;', '/'))
            if img_match:
                img_path = img_match.group(1)
                if img_path.startswith('/'):
                    image_url = f"https://www.hoogvliet.com{img_path}"
                else:
                    image_url = img_path

            # Fallback: construct URL from offer ID
            if not image_url and offer_id.startswith('2025'):
                year = offer_id[:4]
                week = offer_id[4:6]
                image_url = f"{OFFER_IMAGE_BASE}/{year}/{week}/230px172px/{offer_id}.jpg"

        return [{
            'id': offer_id,
            'name': main_name,
            'brand': main_brand,
            'package_description': package_description,
            'offer_price': offer_price,
            'normal_price': normal_price,
            'unit': unit,
            'discount_text': discount_text,
            'category': main_category,
            'image_url': image_url,
            'source_url': url,
            'fresh_days': fresh_days,
            'is_vegetarian': is_vegetarian,
            'is_biological': is_biological,
            'is_new': is_new,
            'is_lowest_price': is_lowest_price
        }]

    except Exception as e:
        print(f"  Error extracting {url}: {e}")

    return []


def extract_hoogvliet_folder():
    """Extract all products from Hoogvliet's current weekly folder."""

    print("Fetching Hoogvliet folder...")

    # Get current folder slug
    slug = get_current_folder_slug()
    if not slug:
        print("Could not find current folder!")
        return None

    print(f"Current folder: {slug}")

    # Parse week from slug (folder_2025_50 -> week-50-2025)
    week_match = re.search(r'folder_(\d{4})_(\d+)', slug)
    folder_week = f"week-{week_match.group(2)}-{week_match.group(1)}" if week_match else None

    # Get folder info
    folder_info = get_folder_info(slug)
    print(f"Folder has {folder_info['total_pages']} pages in {folder_info['spreads']} spreads")

    # Get all product URLs from hotspots
    offer_urls = get_all_hotspot_urls(slug, folder_info['total_pages'])
    print(f"Found {len(offer_urls)} offer URLs")

    # Extract product data in parallel
    products = []
    grouped_offers = 0

    print("Extracting product details...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(extract_product_data, url): url for url in offer_urls}

        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result:
                # Result is now a list of products
                if len(result) > 1:
                    grouped_offers += 1
                products.extend(result)
            if (i + 1) % 20 == 0:
                print(f"  Processed {i + 1}/{len(offer_urls)} URLs...")

    print(f"Extracted {len(products)} products from {len(offer_urls)} offers")
    if grouped_offers > 0:
        print(f"  ({grouped_offers} grouped offers expanded into multiple products)")

    # Sort by offer ID
    products.sort(key=lambda x: x.get('id', ''))

    # Data validation - minimum product count check
    MIN_PRODUCTS = 60  # Hoogvliet typically has 80-150 products
    if len(products) < MIN_PRODUCTS:
        raise ValueError(f"VALIDATION FAILED: Hoogvliet returned only {len(products)} products (minimum: {MIN_PRODUCTS}). Website may have changed.")

    # Build output
    output = {
        'supermarket': 'Hoogvliet',
        'folder_week': folder_week,
        'extracted_at': datetime.now().isoformat(),
        'source_url': f'{FOLDER_BASE_URL}/{slug}/',
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
    archive_file = f"{archive_dir}/folder_data_week_{week_num}_hoogvliet.json"
    with open(archive_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved to: {OUTPUT_FILE}")
    print(f"Archived to: {archive_file}")

    return output


if __name__ == "__main__":
    extract_hoogvliet_folder()
