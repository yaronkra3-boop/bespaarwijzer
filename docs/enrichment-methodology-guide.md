# BespaarWijzer Product Enrichment Methodology Guide

**Version:** 2.0
**Date:** 2025-12-14
**Status:** Production Ready

---

## Overview

This guide documents the methodology for categorizing supermarket products from multiple sources (Albert Heijn, Jumbo, Dirk, Hoogvliet, Lidl) into a consistent BespaarWijzer taxonomy.

### The Problem

Each supermarket uses different category names for the same products:
- Albert Heijn: "Vlees, kip en vis"
- Jumbo: "Vlees, vis en vega"
- Dirk: "Vlees & vis"
- Hoogvliet: "Kaas, vleeswaren, tapas"

Pure automation (keyword matching on product names) causes many false positives:
- "Hertog" beer matched "hert" (deer) -> wrongly categorized as meat
- "Garnier" shampoo matched "garnaal" (shrimp) -> wrongly categorized as fish
- "Mango" drink matched fruit -> wrongly categorized as produce

### The Solution: Category-First with Name-Based Overrides

We use a **two-phase approach**:

1. **Phase 1: Category Path Matching** - Trust the supermarket's original category as the primary signal
2. **Phase 2: Name-Based Overrides** - Correct specific known mismatches using product name keywords

---

## Architecture

### File: `enrich_v2.py`

The enrichment script has three main components:

```
┌─────────────────────────────────────────────────────────────┐
│                    CATEGORY_MAPPING                          │
│  Ordered list of (keyword, category, subcategory) tuples     │
│  ORDER MATTERS - first match wins                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               categorize_by_original_category()              │
│  Matches supermarket category path against CATEGORY_MAPPING  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               Name-Based Override Rules                      │
│  Corrects specific known mismatches using product name       │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Category Path Matching

### How It Works

The `CATEGORY_MAPPING` is an ordered list of tuples. For each product, we:
1. Get the supermarket's original category path (e.g., "Vlees, vis en vega")
2. Convert to lowercase
3. Check each tuple in order - first match wins
4. Return the matched (category, subcategory)

### Critical Rule: Order Matters!

More specific patterns MUST come before generic ones.

**Example Problem:**
```python
# BAD - "vis" matches before "vleeswaren" for "Vlees & vis/Vleeswaren"
("vis", "vis", "verse_vis"),
("vleeswaren", "vlees", "vleeswaren"),

# GOOD - "vleeswaren" checked first
("vleeswaren", "vlees", "vleeswaren"),
("vis", "vis", "verse_vis"),
```

### Category Mapping Sections

The mapping is organized in priority order:

```python
CATEGORY_MAPPING = [
    # 1. SPECIFIC SUBCATEGORY PATTERNS (highest priority)
    ("vleeswaren", "vlees", "vleeswaren"),  # Before /vis
    ("diepvries vis", "vis", "verse_vis"),
    ("/kaas/", "zuivel", "kaas"),           # Path-specific

    # 2. DRANKEN (Beverages)
    ("bier", "dranken", "alcohol"),
    ("frisdrank", "dranken", "frisdrank"),

    # 3. VERZORGING (Personal Care)
    ("drogisterij", "verzorging", "lichaam"),

    # 4. HUISHOUDEN (Household)
    ("huishoud", "huishouden", "schoonmaak"),

    # 5. DIEPVRIES (Frozen)
    ("diepvries", "diepvries", "kant_klaar"),

    # 6. VLEES (Meat) - before generic "vis"
    ("vlees", "vlees", "rund"),

    # 7. VIS (Fish) - careful with generic patterns
    # Note: Generic "vis" removed because "Vlees & vis" is not fish-only

    # 8-12. Other categories (zuivel, groente, brood, snoep, conserven)
]
```

---

## Phase 2: Name-Based Override Rules

After category path matching, we apply name-based corrections for known mismatches.

### Fish Products

Products with fish names should be in vis category, regardless of supermarket category:

```python
# Skip pet food
is_pet_food = any(pet in product_name for pet in ['katten', 'honden'])

if not is_pet_food:
    fish_keywords = ['zalm', 'tonijn', 'garnaal', 'kabeljauw', 'haring',
                     'makreel', 'pangasius', 'mosselen', 'gamba']
    if any(kw in product_name for kw in fish_keywords):
        if 'salade' in product_name:
            # Fish salads go to conserven
            cat_id = 'conserven_houdbaar'
        else:
            cat_id = 'vis'
```

### Vlees Category Corrections

Products in vlees that shouldn't be:

```python
if cat_id == 'vlees':
    # Meat indicators - if present, keep in vlees
    meat_indicators = ['ham', 'kip', 'spek', 'bacon', 'worst', 'schnitzel',
                      'burger', 'filet', 'carpaccio', 'serrano']
    has_meat = any(mi in product_name for mi in meat_indicators)

    # Pure cheese (no meat) -> zuivel
    if 'kaas' in product_name and not has_meat:
        if any(brand in product_name for brand in ['président', 'boursin', 'koggelandse']):
            cat_id = 'zuivel'

    # Dips -> conserven
    if any(kw in product_name for kw in ['hummus', 'tzatziki', 'guacamole']):
        cat_id = 'conserven_houdbaar'

    # Snacks -> snoep_snacks
    if any(kw in product_name for kw in ['borrelnoot', 'nootjes', 'chips']):
        cat_id = 'snoep_snacks'
```

### Other Category Corrections

```python
# Zuivel corrections
if cat_id == 'zuivel':
    if 'pindakaas' in product_name:
        cat_id = 'brood_bakkerij'  # Breakfast spread
    if 'heinz' in product_name or 'wijko' in product_name:
        cat_id = 'conserven_houdbaar'  # Sauce brands

# Brood_bakkerij corrections
if cat_id == 'brood_bakkerij':
    if 'lotus' in product_name or 'speculoos' in product_name:
        cat_id = 'snoep_snacks'  # Cookies

# Diepvries corrections
if cat_id == 'diepvries':
    if any(kw in product_name for kw in ['stol', 'tulband', 'chinois']):
        cat_id = 'brood_bakkerij'  # Pastries, not frozen
    if 'verspakket' in product_name:
        cat_id = 'conserven_houdbaar'  # Fresh meal kits

# Groente_fruit corrections
if cat_id == 'groente_fruit':
    if 'hak ' in product_name:
        cat_id = 'conserven_houdbaar'  # Canned vegetables
    if 'biscuit' in product_name:
        cat_id = 'snoep_snacks'  # Cookies
```

---

## Quality Assurance Process

### Step-by-Step Verification

For each category, run this verification process:

1. **List all products in category**
```python
cat_products = [p for p in products if p.get('_bw_category') == 'vis']
```

2. **Identify suspicious items using keyword checks**
```python
non_fish_keywords = ['kip', 'varken', 'rund', 'ham', 'worst']
for p in cat_products:
    name = p.get('name', '').lower()
    if any(kw in name for kw in non_fish_keywords):
        print(f"SUSPICIOUS: {p.get('name')}")
```

3. **Analyze original category paths**
```python
for p in suspicious:
    print(f"Name: {p.get('name')}")
    print(f"Orig: {p.get('category')}")
    print(f"Decision: Should be in ___ because ___")
```

4. **Add correction rule if needed**

5. **Re-run enrichment and verify**

### Verification Commands

```bash
# Run enrichment
python3 enrich_v2.py

# Check specific category
python3 -c "
import json
with open('../app/products.json') as f:
    products = json.load(f)
for p in products:
    if p.get('_bw_category') == 'vis':
        print(p.get('name')[:50])
"
```

---

## Category Taxonomy

### 12 Main Categories

| ID | Dutch Name | Products | Description |
|---|---|---|---|
| vlees | Vlees | 208 | Meat, meat products, vegetarian alternatives |
| vis | Vis & Zeevruchten | 40 | Fish, seafood |
| zuivel | Zuivel & Eieren | 222 | Dairy products, eggs |
| groente_fruit | Groente & Fruit | 85 | Fresh produce |
| brood_bakkerij | Brood & Bakkerij | 97 | Bread, pastries |
| dranken | Dranken | 763 | Beverages (alcohol, soft drinks, coffee) |
| diepvries | Diepvries | 63 | Frozen products |
| conserven_houdbaar | Conserven & Houdbaar | 307 | Canned goods, dry goods, sauces |
| snoep_snacks | Snoep & Snacks | 207 | Candy, chips, cookies |
| verzorging | Verzorging | 218 | Personal care |
| huishouden | Huishouden | 134 | Household, cleaning, pets |
| baby_kind | Baby & Kind | 1 | Baby products |

### Subcategories

Each main category has subcategories (e.g., vlees has: rund, varken, kip, vleeswaren, vleesvervangers).

---

## Key Principles

### 1. Category Defines Identity

A product's category should reflect **what it IS**, not its ingredients:
- Mango drink in "Dranken" -> dranken (not groente_fruit)
- Palm soap in "Drogisterij" -> verzorging (not groente_fruit)
- Chicken salad in "Vleeswaren" -> vlees (not groente_fruit)

### 2. Supermarket Category is Primary Signal

Trust the supermarket's categorization as the starting point. They put the product where customers expect to find it.

### 3. Name-Based Overrides for Known Issues

Only use product name matching for:
- Correcting clear mismatches (fish products in vlees category)
- Products where supermarket category is ambiguous ("Vlees, vis en vega")
- Specific brand patterns (Président = cheese, Hak = conserved vegetables)

### 4. Name-Based Fallback for "Overig" and Empty Categories

Products from "Overig", "Tijdelijk assortiment", or empty categories don't have useful category paths. Use brand/product name matching as a **fallback** when `cat_id is None`:

```python
if cat_id is None:
    # Brand-based categorization
    if any(kw in product_name for kw in ['hertog jan', 'leffe', 'baileys']):
        cat_id, subcat_id = 'dranken', 'alcohol'
    if any(kw in product_name for kw in ['ariel', 'ajax', 'robijn']):
        cat_id, subcat_id = 'huishouden', 'schoonmaak'
```

**Key brand mappings:**
| Brand | Category |
|---|---|
| Hertog Jan, Leffe, Kordaat, Park Villa, Baileys | dranken |
| Ariel, Ajax, Lenor, Robijn, Dreft, Witte Reus | huishouden |
| Doritos, Celebrations, Kinder, LU Tuc | snoep_snacks |
| Ben & Jerry's, Viennetta | diepvries |
| Nutella | brood_bakkerij |
| Conimex, Jean Bâton, Calvé, Hak | conserven_houdbaar |
| Becel, Monchou | zuivel |
| AntaFlu, Gillette, Axe | verzorging |

### 5. Order in CATEGORY_MAPPING is Critical

More specific patterns before generic ones. Test changes carefully.

### 6. Avoid Over-Matching

Don't match on short/common keywords:
- BAD: "vis" matches "televisie", "visite"
- GOOD: Use path-specific like "/vis" or check context

---

## Step 7: Automated Category Verification

After enrichment, run the verification system to catch mismatches:

```bash
cd /Users/yaronkra/Jarvis/tickets/011-product-master-data/dev/pipeline
python3 verify_categories.py
```

### What It Does
- Checks all 12 categories in parallel
- Flags products with suspicious keywords that don't have valid category keywords
- Generates reports in `verification_reports/` folder
- Prints summary showing flagged items per category

### Output Example
```
CATEGORY VERIFICATION SUMMARY
Vlees                     |  213 products | ⚠ 2 flagged
Vis & Zeevruchten         |   42 products | ✓
Zuivel & Eieren           |  224 products | ⚠ 2 flagged
...
TOTAL FLAGGED: 17 products need review
```

### Handling Flagged Products
1. Review the flagged products in the detailed output
2. Determine if they're false positives (e.g., "Verstegen" contains "vers" but it's a brand)
3. For real mismatches, add correction rules to `enrich_v2.py`
4. Re-run enrichment and verification

### Single Category Verification
```bash
python3 verify_categories.py --category vlees
```

---

## Maintenance Workflow

### When Adding New Supermarket Data

1. Run enrichment on new data
2. Check "Uncategorized" count
3. Add new patterns to CATEGORY_MAPPING for uncategorized
4. **Run verification**: `python3 verify_categories.py`
5. Review flagged products
6. Add name-based overrides as needed
7. Re-run enrichment and verification until clean

### When Categories Look Wrong

1. Identify the problematic products
2. Check their original category paths
3. Determine if issue is:
   - Missing pattern in CATEGORY_MAPPING -> add it
   - Wrong order in CATEGORY_MAPPING -> reorder
   - Need name-based override -> add to override section
4. Test and verify

---

## Files Reference

| File | Purpose |
|---|---|
| `enrich_v2.py` | Main enrichment script |
| `products.json` | Output: enriched products with _bw_* fields |
| `taxonomy.json` | Category definitions (reference only in v2) |
| `aggregated_data.json` | Input: raw supermarket data |

---

## Enriched Fields

Each product gets these fields added:

| Field | Type | Example |
|---|---|---|
| `_bw_category` | string | "vlees" |
| `_bw_subcategory` | string | "kip" |
| `_bw_category_name` | string | "Vlees" |
| `_bw_subcategory_name` | string | "Kip & Gevogelte" |

The `_bw_` prefix ensures no conflict with original supermarket data.

---

*Document Version: 2.1 - Category-First with Name-Based Overrides and Fallbacks*
*Updated: 2025-12-14 - Added name-based fallback rules for "Overig" products*
