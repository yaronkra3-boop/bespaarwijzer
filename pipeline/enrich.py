#!/usr/bin/env python3
"""
BespaarWijzer Product Enrichment Script

Enriches products with consistent categories from our taxonomy.
Uses fuzzy matching to categorize products from all supermarkets.

Usage:
    cd /Users/yaronkra/Jarvis/bespaarwijzer/pipeline
    python3 enrich.py
"""

import json
import re
from pathlib import Path
from collections import Counter

# Paths
BASE_PATH = Path("/Users/yaronkra/Jarvis/bespaarwijzer")
PIPELINE_PATH = BASE_PATH / "pipeline"
DATA_PATH = PIPELINE_PATH / "data"

TAXONOMY_FILE = DATA_PATH / "taxonomy.json"
PRODUCTS_INPUT = PIPELINE_PATH / "output" / "aggregated_data.json"
MASTER_DB_FILE = DATA_PATH / "master_products.json"


def load_taxonomy():
    """Load the category taxonomy."""
    with open(TAXONOMY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_text(text):
    """Normalize text for matching."""
    if not text:
        return ""
    text = text.lower()
    # Remove special characters but keep spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def tokenize(text):
    """Split text into tokens."""
    return set(normalize_text(text).split())


def match_keywords(product_tokens, keywords):
    """Check how many keywords match the product tokens."""
    matches = 0
    for keyword in keywords:
        keyword_tokens = set(normalize_text(keyword).split())
        if keyword_tokens & product_tokens:
            matches += 1
    return matches


def categorize_product(product, taxonomy):
    """
    Determine the best category and subcategory for a product.

    Returns tuple: (category_id, subcategory_id, confidence_score)
    """
    # Combine product fields for matching
    name = product.get('name', '')
    brand = product.get('brand', '')
    category_orig = product.get('category', '')
    department = product.get('department', '')
    webgroup = product.get('webgroup', '')

    # Create searchable text
    search_text = f"{name} {brand} {category_orig} {department} {webgroup}"
    product_tokens = tokenize(search_text)

    best_match = None
    best_score = 0

    # First try: match subcategory keywords (most specific)
    for cat_id, cat_data in taxonomy['categories'].items():
        for subcat_id, subcat_data in cat_data.get('subcategories', {}).items():
            keywords = subcat_data.get('keywords', [])
            score = match_keywords(product_tokens, keywords)

            if score > best_score:
                best_score = score
                best_match = (cat_id, subcat_id, score)

    # Second try: if no subcategory match, try category keywords (broader)
    if best_score == 0:
        for cat_id, cat_data in taxonomy['categories'].items():
            cat_keywords = cat_data.get('category_keywords', [])
            score = match_keywords(product_tokens, cat_keywords)

            if score > 0:
                # Assign to first subcategory of matched category
                subcats = list(cat_data.get('subcategories', {}).keys())
                subcat_id = subcats[0] if subcats else None
                best_match = (cat_id, subcat_id, score)
                best_score = score
                break  # Take first category match

    return best_match if best_match else (None, None, 0)


def detect_special_labels(product, taxonomy):
    """Detect special labels (vegetarian, vegan, bio, etc.)."""
    name = product.get('name', '')
    labels = []

    name_lower = normalize_text(name)

    for label_id, label_data in taxonomy.get('special_labels', {}).items():
        for keyword in label_data.get('keywords', []):
            if keyword in name_lower:
                labels.append(label_id)
                break

    # Also check existing product flags
    if product.get('is_vegetarian'):
        if 'vegetarian' not in labels:
            labels.append('vegetarian')
    if product.get('is_biological'):
        if 'biological' not in labels:
            labels.append('biological')

    return labels


def create_product_signature(product):
    """
    Create a unique signature for product matching.
    Used to identify the same product across different supermarkets.
    """
    name = normalize_text(product.get('name', ''))
    brand = normalize_text(product.get('brand', ''))

    # Extract key identifiers
    # Remove common supermarket-specific prefixes
    name = re.sub(r'^(ah|jumbo|dirk|lidl|hoogvliet)\s+', '', name)

    # Create signature from brand + key name words
    signature_parts = []
    if brand:
        signature_parts.append(brand)

    # Get significant words from name (skip common words)
    skip_words = {'de', 'het', 'van', 'en', 'met', 'of', 'per', 'stuk', 'gram', 'ml', 'liter', 'kg'}
    name_words = [w for w in name.split() if w not in skip_words and len(w) > 2]
    signature_parts.extend(name_words[:3])  # Take first 3 significant words

    return '_'.join(signature_parts)


def enrich_products(products, taxonomy):
    """Enrich all products with category information."""
    enriched = []
    category_stats = Counter()
    uncategorized = []

    for product in products:
        # Get category
        cat_id, subcat_id, confidence = categorize_product(product, taxonomy)

        # Get special labels
        labels = detect_special_labels(product, taxonomy)

        # Create product signature
        signature = create_product_signature(product)

        # Build enriched product (only add our fields)
        enriched_product = {
            **product,
            '_bw_category': cat_id,
            '_bw_subcategory': subcat_id,
            '_bw_confidence': confidence,
            '_bw_labels': labels,
            '_bw_signature': signature
        }

        # Add friendly category names for search
        if cat_id:
            cat_data = taxonomy['categories'].get(cat_id, {})
            enriched_product['_bw_category_name'] = cat_data.get('name_nl', '')
            if subcat_id:
                subcat_data = cat_data.get('subcategories', {}).get(subcat_id, {})
                enriched_product['_bw_subcategory_name'] = subcat_data.get('name_nl', '')

        enriched.append(enriched_product)

        # Track statistics
        if cat_id:
            category_stats[cat_id] += 1
        else:
            uncategorized.append(product.get('name', 'Unknown'))

    return enriched, category_stats, uncategorized


def build_master_database(enriched_products):
    """
    Build a master product database from enriched products.
    Groups products by signature to identify same products across stores.
    """
    master_db = {}

    for product in enriched_products:
        signature = product.get('_bw_signature', '')
        if not signature:
            continue

        if signature not in master_db:
            master_db[signature] = {
                'signature': signature,
                'canonical_name': product.get('name', ''),
                'brand': product.get('brand', ''),
                'category': product.get('_bw_category'),
                'subcategory': product.get('_bw_subcategory'),
                'labels': product.get('_bw_labels', []),
                'seen_at': [],
                'first_seen': None,
                'times_seen': 0
            }

        # Track where this product appears
        store = product.get('supermarket', 'Unknown')
        if store not in master_db[signature]['seen_at']:
            master_db[signature]['seen_at'].append(store)

        master_db[signature]['times_seen'] += 1

    return master_db


def main():
    print("=" * 60)
    print("BespaarWijzer Product Enrichment")
    print("=" * 60)
    print()

    # Load taxonomy
    print(f"Loading taxonomy: {TAXONOMY_FILE}")
    taxonomy = load_taxonomy()
    num_categories = len(taxonomy['categories'])
    num_subcategories = sum(len(cat.get('subcategories', {})) for cat in taxonomy['categories'].values())
    print(f"  Categories: {num_categories}")
    print(f"  Subcategories: {num_subcategories}")
    print()

    # Load products
    print(f"Loading products: {PRODUCTS_INPUT}")
    with open(PRODUCTS_INPUT, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data.get('products', [])
    print(f"  Found {len(products)} products")
    print()

    # Enrich products
    print("Enriching products with categories...")
    enriched, category_stats, uncategorized = enrich_products(products, taxonomy)

    # Print statistics
    print()
    print("Category distribution:")
    for cat_id in sorted(category_stats.keys()):
        cat_name = taxonomy['categories'].get(cat_id, {}).get('name_nl', cat_id)
        count = category_stats[cat_id]
        pct = count / len(products) * 100
        print(f"  {cat_name}: {count} ({pct:.1f}%)")

    uncategorized_count = len(uncategorized)
    if uncategorized_count > 0:
        print(f"\n  Uncategorized: {uncategorized_count} ({uncategorized_count/len(products)*100:.1f}%)")
        if uncategorized_count <= 10:
            for name in uncategorized:
                print(f"    - {name}")
        else:
            print(f"    (showing first 10)")
            for name in uncategorized[:10]:
                print(f"    - {name}")

    # Build master database
    print()
    print("Building master product database...")
    master_db = build_master_database(enriched)
    print(f"  Unique products identified: {len(master_db)}")

    # Count products appearing in multiple stores
    multi_store = sum(1 for p in master_db.values() if len(p['seen_at']) > 1)
    print(f"  Products in multiple stores: {multi_store}")

    # Save master database
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    print(f"\nSaving master database: {MASTER_DB_FILE}")
    with open(MASTER_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(master_db.values()), f, ensure_ascii=False, indent=2)

    # Update aggregated data with enriched products
    data['products'] = enriched
    enriched_output = PIPELINE_PATH / "output" / "enriched_data.json"
    print(f"Saving enriched data: {enriched_output}")
    with open(enriched_output, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    print()
    print("=" * 60)
    print("Enrichment complete!")
    print("=" * 60)
    print()
    print("Files created:")
    print(f"  - {MASTER_DB_FILE}")
    print(f"  - {enriched_output}")
    print()

    return True


if __name__ == "__main__":
    main()
