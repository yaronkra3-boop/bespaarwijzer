#!/usr/bin/env python3
"""
BespaarWijzer Transform Script

Transforms aggregated_data.json into app-ready products.json and folder-validity.json.
Part of the unified BespaarWijzer pipeline.

Usage:
    cd /Users/yaronkra/Jarvis/bespaarwijzer/pipeline
    python3 transform.py

Prerequisites:
    - Run aggregate.py first to get fresh data
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Paths
BASE_PATH = Path("/Users/yaronkra/Jarvis/bespaarwijzer")
PIPELINE_PATH = BASE_PATH / "pipeline"
APP_PATH = BASE_PATH / "app"

INPUT_FILE = PIPELINE_PATH / "output" / "aggregated_data.json"
ENRICHED_FILE = PIPELINE_PATH / "output" / "enriched_data.json"
PRODUCTS_OUTPUT = APP_PATH / "products.json"
VALIDITY_OUTPUT = APP_PATH / "folder-validity.json"


def calculate_discount_percentage(offer_price, normal_price):
    """Calculate discount percentage."""
    if offer_price and normal_price and normal_price > offer_price:
        return round((1 - offer_price / normal_price) * 100)
    return 0


def extract_unit_info(package_desc, name):
    """Extract unit count, volume, and comparison price info."""
    text = f"{package_desc} {name}".lower()

    result = {
        '_unit_count': 1,
        '_unit_price': None,
        '_volume_liters': None,
        '_comparison_price': None,
        '_comparison_unit': 'stuk'
    }

    # Multi-pack patterns: "6 x 330 ml", "4-pack", etc.
    multi_match = re.search(r'(\d+)\s*[x×]\s*(\d+(?:[,\.]\d+)?)\s*(ml|cl|l|liter|gram|g|kg)', text)
    if multi_match:
        result['_unit_count'] = int(multi_match.group(1))
    else:
        pack_match = re.search(r'(\d+)[-\s]?(?:pak|pack|stuks|blikjes|flesjes)', text)
        if pack_match:
            result['_unit_count'] = int(pack_match.group(1))

    # Volume in liters
    vol_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*(ml|cl|l|liter)', text)
    if vol_match:
        amount = float(vol_match.group(1).replace(',', '.'))
        unit = vol_match.group(2)
        if unit == 'ml':
            result['_volume_liters'] = amount / 1000
        elif unit == 'cl':
            result['_volume_liters'] = amount / 100
        else:
            result['_volume_liters'] = amount

    return result


def extract_validity_dates(products, folder_validity=None):
    """Extract validity dates per supermarket.

    Uses folder_validity from aggregated data first (most reliable),
    then falls back to product-level validity fields.

    Returns dict with format expected by frontend:
    {
        "Albert Heijn": {"start_date": "2025-12-13", "end_date": "2025-12-19"},
        ...
    }
    """
    validity = {}

    # First, use the folder_validity from aggregated data (most reliable)
    if folder_validity:
        for store, dates in folder_validity.items():
            if isinstance(dates, dict):
                # Already in correct format: {'start_date': '...', 'end_date': '...'}
                validity[store] = dates
            elif isinstance(dates, str):
                # Parse string format "2025-12-10 - 2025-12-14" into dict
                parts = dates.split(' - ')
                if len(parts) == 2:
                    validity[store] = {'start_date': parts[0].strip(), 'end_date': parts[1].strip()}

    # Then fill in any missing stores from product-level validity
    for p in products:
        store = p.get('supermarket')
        valid = p.get('validity', '')

        if store and valid and store not in validity:
            # Parse product validity string (e.g., "2025-12-10T00:00:00.000Z - 2025-12-14T23:59:00.000Z")
            parts = valid.split(' - ')
            if len(parts) == 2:
                start = parts[0].strip().split('T')[0]  # Remove time portion
                end = parts[1].strip().split('T')[0]
                validity[store] = {'start_date': start, 'end_date': end}

    return validity


def process_products(products):
    """Process products and create grouped structure."""

    # Group products by offer_group_id
    groups = defaultdict(list)
    ungrouped = []

    for p in products:
        group_id = p.get('offer_group_id')
        if group_id:
            groups[group_id].append(p)
        else:
            ungrouped.append(p)

    output_products = []

    # Process grouped offers
    for group_id, group_products in groups.items():
        if len(group_products) == 1:
            ungrouped.append(group_products[0])
            continue

        first = group_products[0]

        # Extract common brand
        brands = set(p.get('brand', '') for p in group_products if p.get('brand'))
        common_brand = brands.pop() if len(brands) == 1 else first.get('brand', '')
        group_name = common_brand if common_brand else first.get('name', 'Aanbieding')

        # Build variants list
        variants = []
        for p in group_products:
            variants.append({
                'id': p.get('id'),
                'name': p.get('name'),
                'image_url': p.get('image_url', ''),
                'source_url': p.get('source_url', ''),
                'brand': p.get('brand', ''),
                'package_description': p.get('package_description', '')
            })

        discount_pct = calculate_discount_percentage(first.get('offer_price'), first.get('normal_price'))
        unit_info = extract_unit_info(first.get('package_description', ''), first.get('name', ''))

        # Preserve enrichment fields from first product
        enrichment_fields = {k: v for k, v in first.items() if k.startswith('_bw_')}

        grouped_product = {
            'supermarket': first.get('supermarket'),
            'id': group_id,
            'name': group_name,
            'brand': common_brand,
            'package_description': first.get('package_description', ''),
            'offer_price': first.get('offer_price'),
            'normal_price': first.get('normal_price'),
            'discount_text': first.get('discount_text', ''),
            'category': first.get('category', ''),
            'department': first.get('department', ''),
            'webgroup': first.get('webgroup', ''),
            'image_url': first.get('image_url', ''),
            'source_url': first.get('source_url', ''),
            'validity': first.get('validity', ''),
            'is_vegetarian': first.get('is_vegetarian', False),
            'is_biological': first.get('is_biological', False),
            'nutriscore': first.get('nutriscore'),
            'requires_card': first.get('requires_card', False),
            'discount_percentage': discount_pct,
            'is_grouped_offer': True,
            'variant_count': len(group_products),
            'variants': variants,
            **unit_info,
            **enrichment_fields
        }

        output_products.append(grouped_product)

    # Process ungrouped products
    for p in ungrouped:
        discount_pct = calculate_discount_percentage(p.get('offer_price'), p.get('normal_price'))
        unit_info = extract_unit_info(p.get('package_description', ''), p.get('name', ''))

        # Preserve enrichment fields
        enrichment_fields = {k: v for k, v in p.items() if k.startswith('_bw_')}

        product = {
            'supermarket': p.get('supermarket'),
            'id': p.get('id'),
            'name': p.get('name', ''),
            'brand': p.get('brand', ''),
            'package_description': p.get('package_description', ''),
            'offer_price': p.get('offer_price'),
            'normal_price': p.get('normal_price'),
            'discount_text': p.get('discount_text', ''),
            'category': p.get('category', ''),
            'department': p.get('department', ''),
            'webgroup': p.get('webgroup', ''),
            'image_url': p.get('image_url', ''),
            'source_url': p.get('source_url', ''),
            'validity': p.get('validity', ''),
            'is_vegetarian': p.get('is_vegetarian', False),
            'is_biological': p.get('is_biological', False),
            'nutriscore': p.get('nutriscore'),
            'requires_card': p.get('requires_card', False),
            'variants': p.get('variants', []),
            'discount_percentage': discount_pct,
            'is_grouped_offer': False,
            'variant_count': 0,
            **unit_info,
            **enrichment_fields
        }

        output_products.append(product)

    # Sort by supermarket, then by discount
    output_products.sort(key=lambda x: (x.get('supermarket', ''), -(x.get('discount_percentage', 0))))

    return output_products


def run_enrichment():
    """Run the enrichment script to categorize products."""
    import subprocess
    import sys

    enrich_script = PIPELINE_PATH / "enrich_v2.py"
    if not enrich_script.exists():
        print(f"WARNING: Enrichment script not found: {enrich_script}")
        return False

    print("Running product enrichment (v2)...")
    result = subprocess.run([sys.executable, str(enrich_script)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: Enrichment failed: {result.stderr}")
        return False

    # Print enrichment output
    if result.stdout:
        for line in result.stdout.split('\n'):
            if line.strip():
                print(f"  {line}")

    return True


def main():
    print("=" * 60)
    print("BoodschapWijzer Weekly Update")
    print("=" * 60)
    print()

    # Check if input file exists
    if not INPUT_FILE.exists():
        print(f"ERROR: Input file not found: {INPUT_FILE}")
        print()
        print("Please run the aggregator first:")
        print("  cd /Users/yaronkra/Jarvis/tickets/001-supermarket")
        print("  python3 aggregate.py")
        return False

    # Run enrichment first
    if not run_enrichment():
        print("WARNING: Enrichment failed, using raw aggregated data")
        use_enriched = False
    else:
        use_enriched = ENRICHED_FILE.exists()

    # Load data (prefer enriched if available)
    input_file = ENRICHED_FILE if use_enriched else INPUT_FILE
    print(f"Loading: {input_file}")
    with open(input_file, 'r') as f:
        data = json.load(f)

    products = data.get('products', [])
    folder_validity = data.get('folder_validity', {})
    print(f"Found {len(products)} products in aggregated data")
    print()

    # Extract validity dates (use folder_validity from aggregated data first)
    validity = extract_validity_dates(products, folder_validity)
    print("Validity dates per store:")
    for store, valid in sorted(validity.items()):
        if isinstance(valid, dict):
            print(f"  - {store}: {valid.get('start_date', '')} - {valid.get('end_date', '')}")
        else:
            print(f"  - {store}: {valid}")
    print()

    # Process products
    output_products = process_products(products)
    grouped_count = sum(1 for p in output_products if p.get('is_grouped_offer'))
    individual_count = len(output_products) - grouped_count

    print(f"Processed: {len(output_products)} products")
    print(f"  - {grouped_count} grouped offers")
    print(f"  - {individual_count} individual products")
    print()

    # Save products.json
    print(f"Saving: {PRODUCTS_OUTPUT}")
    with open(PRODUCTS_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output_products, f, ensure_ascii=False)

    file_size = PRODUCTS_OUTPUT.stat().st_size / 1024
    print(f"  Size: {file_size:.1f} KB")

    # Save folder-validity.json
    print(f"Saving: {VALIDITY_OUTPUT}")
    with open(VALIDITY_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(validity, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print("Update complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Start local server: python3 -m http.server 8080")
    print("  2. Open: http://localhost:8080/boodschapwijzer-app.html")
    print("  3. Verify products load correctly")
    print()

    return True


if __name__ == "__main__":
    main()
