#!/usr/bin/env python3
"""
Category Verification System for BespaarWijzer Products

This script spawns parallel agents to verify each category.
Each agent checks all products in its assigned category and reports mismatches.

Usage:
    python3 verify_categories.py [--category CATEGORY_ID]

If no category specified, verifies all 12 categories in parallel.
"""

import json
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Paths
BASE_PATH = Path(__file__).parent.parent  # bespaarwijzer folder
PRODUCTS_FILE = BASE_PATH / "app" / "products.json"
REPORTS_DIR = BASE_PATH / "pipeline" / "verification_reports"

# The 12 categories
CATEGORIES = {
    "vlees": {
        "name": "Vlees",
        "belongs": "Meat, poultry, meat products, meat alternatives",
        "suspicious_keywords": ["vis", "zalm", "tonijn", "garnaal", "kaas", "smoothie", "sap", "drank"],
        "valid_keywords": ["ham", "kip", "spek", "bacon", "worst", "schnitzel", "burger", "filet", "gehakt", "rund", "varken", "vega"]
    },
    "vis": {
        "name": "Vis & Zeevruchten",
        "belongs": "Fish, seafood, shellfish",
        "suspicious_keywords": ["kip", "varken", "rund", "ham", "worst", "gehakt", "bacon", "katten", "honden"],
        "valid_keywords": ["zalm", "tonijn", "garnaal", "kabeljauw", "haring", "makreel", "mosselen", "vis"]
    },
    "zuivel": {
        "name": "Zuivel & Eieren",
        "belongs": "Dairy products, eggs, cheese, milk, yogurt, butter",
        "suspicious_keywords": ["saus", "mayonaise", "ketchup", "mosterd"],
        "valid_keywords": ["melk", "kaas", "yoghurt", "ei", "boter", "kwark", "room", "vla"]
    },
    "groente_fruit": {
        "name": "Groente & Fruit",
        "belongs": "Fresh vegetables, fresh fruit",
        "suspicious_keywords": ["sap", "smoothie", "drank", "blik", "conserven", "diepvries", "koek", "biscuit"],
        "valid_keywords": ["appel", "banaan", "tomaat", "komkommer", "sla", "wortel", "ui", "aardappel"]
    },
    "brood_bakkerij": {
        "name": "Brood & Bakkerij",
        "belongs": "Bread, pastries, breakfast cereals, spreads",
        "suspicious_keywords": ["chips", "snoep", "chocolade"],
        "valid_keywords": ["brood", "croissant", "stokbrood", "ontbijt", "muesli", "hagelslag", "pindakaas"]
    },
    "dranken": {
        "name": "Dranken",
        "belongs": "All beverages - alcohol, soft drinks, juice, coffee, tea, water",
        "suspicious_keywords": ["kaas", "vlees", "brood"],
        "valid_keywords": ["bier", "wijn", "cola", "sap", "water", "koffie", "thee", "fris", "energy"]
    },
    "diepvries": {
        "name": "Diepvries",
        "belongs": "Frozen products only - ice cream, frozen meals, frozen vegetables",
        "suspicious_keywords": ["vers", "verse"],
        "valid_keywords": ["ijs", "pizza", "diepvries", "bevroren", "frozen"]
    },
    "conserven_houdbaar": {
        "name": "Conserven & Houdbaar",
        "belongs": "Canned goods, dry goods, sauces, pasta, rice, prepared salads",
        "suspicious_keywords": ["vers", "verse", "diepvries"],
        "valid_keywords": ["blik", "saus", "pasta", "rijst", "soep", "conserven", "houdbaar"]
    },
    "snoep_snacks": {
        "name": "Snoep & Snacks",
        "belongs": "Candy, chocolate, chips, cookies, nuts, snack bars",
        "suspicious_keywords": ["saus", "dip", "brood", "ontbijt"],
        "valid_keywords": ["chips", "chocolade", "snoep", "koek", "noten", "drop", "winegum"]
    },
    "verzorging": {
        "name": "Verzorging",
        "belongs": "Personal care - shampoo, soap, dental, cosmetics, health",
        "suspicious_keywords": ["eten", "drinken", "voeding"],
        "valid_keywords": ["shampoo", "zeep", "tandpasta", "deodorant", "creme", "verzorging"]
    },
    "huishouden": {
        "name": "Huishouden",
        "belongs": "Cleaning products, laundry, pet food, household items",
        "suspicious_keywords": ["eten", "drinken", "voeding"],
        "valid_keywords": ["schoonmaak", "wasmiddel", "afwas", "katten", "honden", "wc", "toiletpapier"]
    },
    "baby_kind": {
        "name": "Baby & Kind",
        "belongs": "Baby products - food, diapers, care",
        "suspicious_keywords": [],
        "valid_keywords": ["baby", "luier", "fles", "speen"]
    }
}


def load_products():
    """Load products from JSON file."""
    with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def verify_category(category_id: str, products: list) -> dict:
    """
    Verify all products in a category.
    Returns a report with flagged items.
    """
    cat_info = CATEGORIES.get(category_id, {})
    cat_products = [p for p in products if p.get('_bw_category') == category_id]

    report = {
        "category_id": category_id,
        "category_name": cat_info.get("name", category_id),
        "total_products": len(cat_products),
        "flagged_products": [],
        "summary": ""
    }

    suspicious_keywords = cat_info.get("suspicious_keywords", [])
    valid_keywords = cat_info.get("valid_keywords", [])

    for product in cat_products:
        name = product.get('name', '').lower()
        original_cat = product.get('category', '')

        # Check for suspicious keywords
        found_suspicious = []
        for kw in suspicious_keywords:
            if kw in name:
                found_suspicious.append(kw)

        # Check if it has valid keywords (reduces false positives)
        has_valid = any(kw in name for kw in valid_keywords)

        # Flag if suspicious and no valid keywords
        if found_suspicious and not has_valid:
            report["flagged_products"].append({
                "name": product.get('name', ''),
                "original_category": original_cat,
                "suspicious_keywords": found_suspicious,
                "reason": f"Contains {found_suspicious} but no valid {category_id} keywords"
            })

    flagged_count = len(report["flagged_products"])
    report["summary"] = f"{flagged_count} of {len(cat_products)} products flagged for review"

    return report


def generate_agent_prompt(category_id: str, products: list) -> str:
    """Generate a prompt for an AI agent to verify a category."""
    cat_info = CATEGORIES.get(category_id, {})
    cat_products = [p for p in products if p.get('_bw_category') == category_id]

    # Build product list
    product_list = []
    for p in cat_products:
        product_list.append(f"- {p.get('name', 'NO NAME')} (orig: {p.get('category', 'N/A')[:40]})")

    prompt = f"""# Category Verification: {cat_info.get('name', category_id)}

## Your Task
Review all {len(cat_products)} products in the **{cat_info.get('name')}** category.
Identify any products that don't belong.

## What Belongs in {cat_info.get('name')}
{cat_info.get('belongs', 'N/A')}

## Products to Review
{chr(10).join(product_list)}

## Instructions
1. Go through each product name
2. For each product, determine: Does this belong in {cat_info.get('name')}?
3. If NOT, specify:
   - Product name
   - Correct category (one of: vlees, vis, zuivel, groente_fruit, brood_bakkerij, dranken, diepvries, conserven_houdbaar, snoep_snacks, verzorging, huishouden, baby_kind)
   - Reason for the change

## Output Format
```
MISPLACED PRODUCTS:
1. [Product Name] -> [Correct Category] (Reason: ...)
2. ...

SUMMARY: X products need to be moved
```

If all products are correct, output:
```
ALL PRODUCTS VERIFIED - No misplacements found
```
"""
    return prompt


def save_report(report: dict, output_dir: Path):
    """Save verification report to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{report['category_id']}_verification.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return output_file


def print_summary(reports: list):
    """Print summary of all verification reports."""
    print("\n" + "=" * 60)
    print("CATEGORY VERIFICATION SUMMARY")
    print("=" * 60)

    total_flagged = 0
    for report in reports:
        flagged = len(report.get("flagged_products", []))
        total_flagged += flagged
        status = "✓" if flagged == 0 else f"⚠ {flagged} flagged"
        print(f"{report['category_name']:25} | {report['total_products']:4} products | {status}")

    print("-" * 60)
    print(f"TOTAL FLAGGED: {total_flagged} products need review")
    print("=" * 60)


def main():
    """Main verification process."""
    print("=" * 60)
    print("BespaarWijzer Category Verification System")
    print("=" * 60)

    # Load products
    print(f"\nLoading products from: {PRODUCTS_FILE}")
    products = load_products()
    print(f"Loaded {len(products)} products")

    # Check for specific category argument
    if len(sys.argv) > 2 and sys.argv[1] == "--category":
        categories_to_verify = [sys.argv[2]]
    else:
        categories_to_verify = list(CATEGORIES.keys())

    print(f"\nVerifying {len(categories_to_verify)} categories...")

    # Run verification for each category
    reports = []
    for cat_id in categories_to_verify:
        print(f"  Verifying {cat_id}...")
        report = verify_category(cat_id, products)
        reports.append(report)

        # Save individual report
        save_report(report, REPORTS_DIR)

    # Print summary
    print_summary(reports)

    # Save combined report
    combined_report = {
        "total_products": len(products),
        "categories_verified": len(categories_to_verify),
        "reports": reports
    }

    combined_file = REPORTS_DIR / "verification_summary.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(combined_report, f, ensure_ascii=False, indent=2)

    print(f"\nReports saved to: {REPORTS_DIR}")

    # Print flagged products details
    total_flagged = sum(len(r.get("flagged_products", [])) for r in reports)
    if total_flagged > 0:
        print("\n" + "=" * 60)
        print("FLAGGED PRODUCTS DETAILS")
        print("=" * 60)
        for report in reports:
            if report.get("flagged_products"):
                print(f"\n--- {report['category_name']} ---")
                for item in report["flagged_products"][:10]:  # Show max 10 per category
                    print(f"  • {item['name'][:50]}")
                    print(f"    Keywords: {item['suspicious_keywords']}")
                if len(report["flagged_products"]) > 10:
                    print(f"  ... and {len(report['flagged_products']) - 10} more")


if __name__ == "__main__":
    main()
