#!/usr/bin/env python3
"""
BespaarWijzer Product Enrichment Script - Version 2
Category-First Approach

Instead of keyword matching on product names (which causes false positives),
we trust the supermarket's original category as the primary signal.

A mango drink is in "Dranken" -> it's a drink, not a fruit.
A soap with "palm" is in "Drogisterij" -> it's personal care, not food.
"""

import json
import re
from pathlib import Path
from collections import Counter

# Paths
BASE_PATH = Path(__file__).parent.parent  # Go up from pipeline to bespaarwijzer folder
PIPELINE_PATH = Path(__file__).parent
DATA_PATH = PIPELINE_PATH / "data"

PRODUCTS_INPUT = PIPELINE_PATH / "output" / "aggregated_data.json"
ENRICHED_OUTPUT = PIPELINE_PATH / "output" / "enriched_data.json"

# =============================================================================
# CATEGORY MAPPING
# =============================================================================
# Map supermarket category keywords to our categories
# Order matters - first match wins
# Format: (keyword_in_original_category, our_category, our_subcategory)

CATEGORY_MAPPING = [
    # ==========================================================================
    # IMPORTANT: Order matters! More specific patterns must come BEFORE generic ones.
    # The LAST part of the category path is usually the most specific.
    # ==========================================================================

    # --- SPECIFIC SUBCATEGORY PATTERNS (check these FIRST) ---
    # These override the main category when present

    # VLEESWAREN must come BEFORE /vis to handle "Vlees & vis/Vleeswaren"
    ("vleeswaren", "vlees", "vleeswaren"),

    # Fish-specific patterns (before generic vlees patterns)
    ("diepvries vis", "vis", "verse_vis"),
    ("diepvries/vis", "vis", "verse_vis"),
    ("/vis", "vis", "verse_vis"),  # If path ends with /Vis
    ("gourmet/vis", "vis", "verse_vis"),
    ("zeevruchten", "vis", "zeevruchten"),

    # KAAS (Cheese) - must come BEFORE vlees to handle "Kaas, vleeswaren, tapas"
    # The path often contains "/Kaas/" which is very specific
    ("/kaas/", "zuivel", "kaas"),
    ("plakken kaas", "zuivel", "kaas"),
    ("geitenkaas", "zuivel", "kaas"),
    ("buitenlandse kaas", "zuivel", "kaas"),
    ("smeerkaas", "zuivel", "kaas"),
    ("geraspte kaas", "zuivel", "kaas"),
    ("kook & saladekazen", "zuivel", "kaas"),

    # SAUZEN (Sauces) - Maggi etc should go to conserven
    ("/sauzen/", "conserven_houdbaar", "sauzen"),
    ("mix voor groente", "conserven_houdbaar", "sauzen"),

    # Salads go to conserven (prepared foods), not zuivel
    ("salades", "conserven_houdbaar", "conserven"),
    ("salade", "conserven_houdbaar", "conserven"),
    ("ei, groentesalades", "conserven_houdbaar", "conserven"),

    # Tapas/dips go to conserven - specific patterns
    ("tapenade", "conserven_houdbaar", "conserven"),
    ("spreads", "conserven_houdbaar", "conserven"),
    ("tapas en borrel", "conserven_houdbaar", "conserven"),
    ("tapas", "conserven_houdbaar", "conserven"),

    # Olijven go to conserven
    ("/olijven", "conserven_houdbaar", "conserven"),

    # Smoothies/juices - check product NAME for smoothie since category is "groente en fruit"
    # This requires a name-based check, not category-based

    # Smoothies/juices in fruit section should go to dranken
    ("smoothie", "dranken", "sap"),
    ("fruitsap", "dranken", "sap"),
    ("sap", "dranken", "sap"),
    ("verse sappen", "dranken", "sap"),

    # --- DRANKEN (Beverages) ---
    ("bier", "dranken", "alcohol"),
    ("wijn", "dranken", "alcohol"),
    ("alcoholvrij", "dranken", "alcohol"),
    ("aperitieven", "dranken", "alcohol"),
    ("frisdrank", "dranken", "frisdrank"),
    ("sappen", "dranken", "sap"),
    ("water", "dranken", "water"),
    ("koffie", "dranken", "koffie_thee"),
    ("thee", "dranken", "koffie_thee"),
    ("dranken", "dranken", "frisdrank"),
    ("energy", "dranken", "frisdrank"),
    ("zuiveldranken", "dranken", "sap"),  # CoolBest etc are drinks

    # --- VERZORGING (Personal Care) ---
    ("drogisterij", "verzorging", "lichaam"),
    ("cosmetica", "verzorging", "gezicht"),
    ("beauty", "verzorging", "gezicht"),
    ("haarverzorging", "verzorging", "haar"),
    ("bad, douche", "verzorging", "lichaam"),
    ("gezondheid", "verzorging", "lichaam"),

    # --- BABY & KIND ---
    ("baby", "baby_kind", "luiers"),

    # --- HUISHOUDEN (Household) ---
    ("huishoud", "huishouden", "schoonmaak"),
    ("huisdier", "huishouden", "huisdier"),
    ("dieren", "huishouden", "huisdier"),
    ("schoonmaak", "huishouden", "schoonmaak"),
    ("toiletreinigers", "huishouden", "schoonmaak"),
    ("wasmiddel", "huishouden", "wasmiddel"),
    ("non-food", "huishouden", "schoonmaak"),

    # --- DIEPVRIES (Frozen) - before other food categories ---
    ("diepvries", "diepvries", "kant_klaar"),
    ("frozen", "diepvries", "kant_klaar"),
    ("ijs", "diepvries", "ijs"),

    # --- VLEES (Meat) - MUST come BEFORE generic "vis" pattern ---
    # Because "Vlees & vis" and "Vlees, vis en vega" contain "vis"
    # Note: vleeswaren is handled at the top (before /vis pattern)
    ("vlees", "vlees", "rund"),
    ("varken", "vlees", "varken"),
    ("kip", "vlees", "kip"),
    ("gehakt", "vlees", "rund"),
    ("rund", "vlees", "rund"),
    ("worst", "vlees", "vleeswaren"),
    ("ham", "vlees", "vleeswaren"),
    ("spek", "vlees", "varken"),
    ("vega", "vlees", "vleesvervangers"),  # Vegetarian meat alternatives

    # --- VIS (Fish) - ONLY specific fish patterns, not generic "vis" ---
    # The word "vis" appears in "Vlees & vis" which is NOT a fish-only category
    # So we REMOVED the generic ("vis", "vis", "verse_vis") pattern

    # --- ZUIVEL (Dairy) - specific patterns only ---
    ("zuivel", "zuivel", "melk"),
    ("eieren", "zuivel", "eieren"),
    ("boter", "zuivel", "boter"),
    ("kaas", "zuivel", "kaas"),  # Only pure kaas, not "kaas, vleeswaren"

    # --- GROENTE & FRUIT ---
    ("groente", "groente_fruit", "groente"),
    ("fruit", "groente_fruit", "fruit"),
    ("aardappel", "groente_fruit", "aardappel"),

    # --- BROOD & BAKKERIJ ---
    ("brood", "brood_bakkerij", "brood"),
    ("bakkerij", "brood_bakkerij", "brood"),
    ("gebak", "brood_bakkerij", "gebak"),
    ("bakproducten", "brood_bakkerij", "brood"),

    # --- SNOEP & SNACKS ---
    ("snoep", "snoep_snacks", "snoep"),
    ("chocolade", "snoep_snacks", "chocolade"),
    ("chips", "snoep_snacks", "chips"),
    ("koek", "snoep_snacks", "koek"),
    ("zoutjes", "snoep_snacks", "chips"),
    ("noten", "snoep_snacks", "chips"),
    ("snacks", "snoep_snacks", "chips"),

    # --- CONSERVEN & HOUDBAAR ---
    ("conserven", "conserven_houdbaar", "conserven"),
    ("soepen", "conserven_houdbaar", "conserven"),
    ("sauzen", "conserven_houdbaar", "sauzen"),
    ("kruiden", "conserven_houdbaar", "kruiden"),
    ("pasta", "conserven_houdbaar", "pasta_rijst"),
    ("rijst", "conserven_houdbaar", "pasta_rijst"),
    ("wereldkeuken", "conserven_houdbaar", "pasta_rijst"),
    ("voorraadkast", "conserven_houdbaar", "conserven"),
    ("houdbaar", "conserven_houdbaar", "conserven"),
    ("oliën", "conserven_houdbaar", "olie_azijn"),
    ("ontbijtgranen", "brood_bakkerij", "ontbijt"),
    ("beleg", "brood_bakkerij", "brood"),
    ("tussendoor", "snoep_snacks", "koek"),

    # --- MAALTIJDEN ---
    ("maaltijden", "diepvries", "kant_klaar"),
    ("verse maaltijden", "diepvries", "kant_klaar"),

    # --- SPECIAL OCCASIONS ---
    ("feestdagen", "diepvries", "kant_klaar"),
    ("kerst", "diepvries", "kant_klaar"),
    ("barbecue", "vlees", "rund"),
    ("gourmet", "vlees", "rund"),
    ("borrel", "snoep_snacks", "chips"),
]

# Category display names
CATEGORY_NAMES = {
    "vlees": "Vlees",
    "vis": "Vis & Zeevruchten",
    "zuivel": "Zuivel & Eieren",
    "groente_fruit": "Groente & Fruit",
    "brood_bakkerij": "Brood & Bakkerij",
    "dranken": "Dranken",
    "diepvries": "Diepvries",
    "conserven_houdbaar": "Conserven & Houdbaar",
    "snoep_snacks": "Snoep & Snacks",
    "verzorging": "Verzorging",
    "huishouden": "Huishouden",
    "baby_kind": "Baby & Kind",
}

SUBCATEGORY_NAMES = {
    "rund": "Rundvlees",
    "varken": "Varkensvlees",
    "kip": "Kip & Gevogelte",
    "vleeswaren": "Vleeswaren",
    "vleesvervangers": "Vleesvervangers",
    "verse_vis": "Verse Vis",
    "zeevruchten": "Zeevruchten",
    "melk": "Melk",
    "yoghurt": "Yoghurt & Kwark",
    "kaas": "Kaas",
    "boter": "Boter & Margarine",
    "eieren": "Eieren",
    "groente": "Verse Groente",
    "fruit": "Vers Fruit",
    "aardappel": "Aardappelen",
    "salade": "Salades",
    "brood": "Brood",
    "gebak": "Gebak & Koek",
    "ontbijt": "Ontbijtgranen",
    "frisdrank": "Frisdrank",
    "sap": "Sap & Smoothie",
    "water": "Water",
    "koffie_thee": "Koffie & Thee",
    "alcohol": "Bier & Wijn",
    "ijs": "IJs",
    "pizza": "Pizza & Snacks",
    "kant_klaar": "Kant-en-klaar",
    "conserven": "Conserven",
    "pasta_rijst": "Pasta & Rijst",
    "sauzen": "Sauzen",
    "kruiden": "Kruiden & Specerijen",
    "olie_azijn": "Olie & Azijn",
    "chocolade": "Chocolade",
    "snoep": "Snoep",
    "chips": "Chips & Noten",
    "koek": "Koekjes",
    "haar": "Haarverzorging",
    "lichaam": "Lichaamsverzorging",
    "gezicht": "Gezichtsverzorging",
    "schoonmaak": "Schoonmaakmiddelen",
    "wasmiddel": "Wasmiddelen",
    "huisdier": "Huisdieren",
    "luiers": "Luiers & Verzorging",
}


def categorize_by_original_category(original_category):
    """
    Map original supermarket category to our category.
    Uses simple keyword matching on the category PATH, not the product name.
    """
    if not original_category:
        return None, None

    cat_lower = original_category.lower()

    for keyword, our_cat, our_subcat in CATEGORY_MAPPING:
        if keyword in cat_lower:
            return our_cat, our_subcat

    return None, None


def enrich_products(products):
    """Enrich all products with category information based on original category."""
    enriched = []
    category_stats = Counter()
    uncategorized = []

    for product in products:
        original_cat = product.get('category', '')
        product_name = product.get('name', '').lower()

        # Get our category based on original supermarket category
        cat_id, subcat_id = categorize_by_original_category(original_cat)

        # =======================================================================
        # NAME-BASED FALLBACK for products with "Overig", "Tijdelijk", or empty category
        # These products don't have useful category paths, so we use product name
        # =======================================================================
        if cat_id is None:
            # --- DRANKEN ---
            dranken_keywords = [
                'hertog jan', 'leffe', 'tripel karmeliet', 'kordaat', 'park villa',
                'baileys', 'grüner veltliner', 'arizona', 'coca-cola', 'bitter lemon',
                'tonic', 'ginger ale', 'nescafé', 'dolce gusto', 'karvan cévitam',
                'maaza', 'spa moments', 'crystal clear'
            ]
            if any(kw in product_name for kw in dranken_keywords):
                cat_id, subcat_id = 'dranken', 'frisdrank'

            # --- HUISHOUDEN ---
            huishouden_keywords = [
                'ariel', 'ajax', 'lenor', 'robijn', 'dreft', 'witte reus',
                'vaatwastabletten', 'toiletpapier', 'batterij', 'alkaline',
                'boeket', 'kerstboom', 'deurhanger', 'kalanchoe', 'keramiek'
            ]
            if any(kw in product_name for kw in huishouden_keywords):
                cat_id, subcat_id = 'huishouden', 'schoonmaak'

            # --- SNOEP_SNACKS ---
            snoep_keywords = [
                'doritos', 'celebrations', 'kinder happy', 'lu tuc', 'cashewnoten',
                'delight bar', 'churro'
            ]
            if any(kw in product_name for kw in snoep_keywords):
                cat_id, subcat_id = 'snoep_snacks', 'chips'

            # --- GROENTE_FRUIT ---
            groente_keywords = [
                'aardbeien', 'kiwi gold', 'cherrytomaten', 'krieltjes',
                'oesterzwammen', 'rode bessen', 'maaltijdsalade'
            ]
            if any(kw in product_name for kw in groente_keywords):
                cat_id, subcat_id = 'groente_fruit', 'groente'
            # Mango as standalone word (not part of another word)
            if 'mango' in product_name and cat_id is None:
                cat_id, subcat_id = 'groente_fruit', 'fruit'

            # --- BROOD_BAKKERIJ ---
            brood_keywords = [
                'breekbrood', 'baguette', 'nutella', 'cronuts', 'sesam volkoren'
            ]
            if any(kw in product_name for kw in brood_keywords):
                cat_id, subcat_id = 'brood_bakkerij', 'brood'

            # --- VLEES ---
            vlees_keywords = [
                'kipshaslick', 'kipsate', 'shoarma', 'schouderkarbonade', 'sukadelappen'
            ]
            if any(kw in product_name for kw in vlees_keywords):
                cat_id, subcat_id = 'vlees', 'rund'

            # --- DIEPVRIES ---
            diepvries_keywords = [
                'viennetta', "ben & jerry", 'verse pizza', 'calzone', 'xxl nutrition'
            ]
            if any(kw in product_name for kw in diepvries_keywords):
                cat_id, subcat_id = 'diepvries', 'ijs'

            # --- VERZORGING ---
            verzorging_keywords = [
                'antaflu', 'axe showergel', 'axe deodorant', 'gillette', 'floralys zakdoekjes'
            ]
            if any(kw in product_name for kw in verzorging_keywords):
                cat_id, subcat_id = 'verzorging', 'lichaam'

            # --- CONSERVEN_HOUDBAAR ---
            conserven_keywords = [
                'conimex', 'boemboe', 'jean bâton', 'calvé', 'hak'
            ]
            if any(kw in product_name for kw in conserven_keywords):
                cat_id, subcat_id = 'conserven_houdbaar', 'sauzen'

            # --- ZUIVEL ---
            zuivel_keywords = ['becel', 'monchou']
            if any(kw in product_name for kw in zuivel_keywords):
                cat_id, subcat_id = 'zuivel', 'boter'

            # --- VIS (from "Vis" original category that wasn't matched) ---
            vis_keywords = ['hollandse nieuwe']
            if any(kw in product_name for kw in vis_keywords):
                cat_id, subcat_id = 'vis', 'verse_vis'

        # Name-based overrides for products that are miscategorized by supermarket
        # Smoothies in "groente en fruit" should be dranken
        if 'smoothie' in product_name and cat_id == 'groente_fruit':
            cat_id, subcat_id = 'dranken', 'sap'

        # Fish products should be in vis category based on product name
        # Skip pet food (kattenvoer, hondenvoer, etc.)
        is_pet_food = any(pet in product_name for pet in ['katten', 'honden', 'kat ', 'hond '])
        if not is_pet_food:
            fish_keywords = ['zalm', 'tonijn', 'garnaal', 'garnalen', 'kabeljauw', 'haring',
                           'makreel', 'pangasius', 'mosselen', 'zeevruchten', 'gamba']
            # Products with these fish names should be in vis, regardless of category
            # (unless they're salads which go to conserven)
            if any(kw in product_name for kw in fish_keywords):
                # Check if it's a salad - salads stay in conserven
                if 'salade' in product_name or 'salad' in product_name:
                    cat_id, subcat_id = 'conserven_houdbaar', 'conserven'
                else:
                    cat_id, subcat_id = 'vis', 'verse_vis'

        # Name-based corrections for products in vlees category that shouldn't be
        if cat_id == 'vlees':
            # Meat indicators - if product has these, it stays in vlees even with "kaas"
            meat_indicators = ['ham', 'kip', 'vlees', 'spek', 'bacon', 'worst', 'schnitzel',
                              'burger', 'filet', 'rolletje', 'carpaccio', 'soufflé', 'serrano']
            has_meat = any(mi in product_name for mi in meat_indicators)

            # Pure cheese products - need to identify cheese that is NOT with meat
            # Cheese brands that are standalone cheese products
            cheese_brands = ['président', 'boursin', 'koggelandse', 'bettine']
            # Check for cheese brands - but "burger" in cheese name is OK (it's burger cheese, not a meat burger)
            if any(brand in product_name for brand in cheese_brands):
                # For président, check if it's cheese slices/plakjes (not an actual burger)
                if 'plakjes' in product_name or 'plak' in product_name:
                    cat_id, subcat_id = 'zuivel', 'kaas'
                elif not has_meat:
                    cat_id, subcat_id = 'zuivel', 'kaas'

            # Pure cheese types (brie, camembert, etc.) without meat
            cheese_types = ['brie', 'camembert', 'geitenkaas', 'abdijkaas', 'kaasfondue',
                           'bieslookkaas', 'roomkaas ananas']
            if any(ct in product_name for ct in cheese_types) and not has_meat:
                cat_id, subcat_id = 'zuivel', 'kaas'

            # Cheese blokjes/kaasblokjes are pure cheese
            if 'kaas' in product_name and 'blokjes' in product_name and not has_meat:
                cat_id, subcat_id = 'zuivel', 'kaas'

            # Other pure cheese patterns
            if 'kaas' in product_name and not has_meat:
                # Specific patterns that are clearly cheese
                if any(kw in product_name for kw in ['heks', 'roomkaas met kruiden',
                                                      'sweet peppers roomkaas', 'koggelandse']):
                    cat_id, subcat_id = 'zuivel', 'kaas'

            # Salads that contain "kaas" go to conserven, not zuivel
            if 'salade' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'

            # Vegetable salads (sellerie, komkommer)
            if any(veg in product_name for veg in ['sellerie', 'komkommer']) and 'salade' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'

            # Dips and spreads that are not meat
            dip_keywords = ['hummus', 'tzatziki', 'aioli', 'guacamole', 'tapenade', 'pesto']
            if any(kw in product_name for kw in dip_keywords):
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'

            # Sauces
            if 'saus' in product_name and 'maggi' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'sauzen'

            # Snacks/noten that got miscategorized
            snack_keywords = ['borrelnoot', 'nootjes', 'chips', 'zoutjes']
            if any(kw in product_name for kw in snack_keywords):
                cat_id, subcat_id = 'snoep_snacks', 'chips'

            # Olijven (olives)
            if 'olijven' in product_name and 'tonijn' not in product_name and 'ansjovis' not in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'

        # Zuivel corrections
        if cat_id == 'zuivel':
            # Allioli/aioli is a sauce, not dairy
            if 'allioli' in product_name or 'aioli' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'sauzen'
            # Pindakaas is a breakfast spread
            if 'pindakaas' in product_name:
                cat_id, subcat_id = 'brood_bakkerij', 'ontbijt'
            # Heinz/Wijko are sauce brands
            if 'heinz' in product_name or 'wijko' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'sauzen'

        # Brood_bakkerij corrections
        if cat_id == 'brood_bakkerij':
            # Lotus Biscoff/speculoos are cookies -> snoep_snacks
            if 'lotus' in product_name or 'speculoos' in product_name or 'biscoff' in product_name:
                cat_id, subcat_id = 'snoep_snacks', 'koek'
            # Hero B'tween bars are snack bars -> snoep_snacks
            if "b'tween" in product_name or 'btween' in product_name:
                cat_id, subcat_id = 'snoep_snacks', 'koek'

        # Diepvries corrections - some items shouldn't be frozen
        if cat_id == 'diepvries':
            # Stol, tulband, chinois are bakery items
            if any(kw in product_name for kw in ['stol', 'tulband', 'chinois', 'slofje']):
                cat_id, subcat_id = 'brood_bakkerij', 'gebak'
            # Verse roomkaas is dairy
            if 'roomkaas' in product_name and 'verse' in product_name:
                cat_id, subcat_id = 'zuivel', 'kaas'
            # Verspakket (fresh meal kits) go to conserven (prepared meals)
            if 'verspakket' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'
            # Verse soep goes to conserven
            if 'verse soep' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'
            # Rijst (rice) is not frozen - goes to conserven
            if 'rijst' in product_name and 'diepvries' not in (original_cat or '').lower():
                cat_id, subcat_id = 'conserven_houdbaar', 'pasta_rijst'

        # Snoep_snacks corrections
        if cat_id == 'snoep_snacks':
            # Dips/sauces that got categorized as snacks -> conserven
            dip_keywords = ['tapenade', 'knoflooksaus', 'pesto', 'guacamole', 'dip']
            if any(kw in product_name for kw in dip_keywords):
                cat_id, subcat_id = 'conserven_houdbaar', 'sauzen'
            # Potato products -> diepvries (likely frozen)
            if 'aardappel' in product_name and 'aviko' in product_name:
                cat_id, subcat_id = 'diepvries', 'kant_klaar'
            # Tulband/cake -> brood_bakkerij
            if 'tulband' in product_name:
                cat_id, subcat_id = 'brood_bakkerij', 'gebak'

        # Groente_fruit corrections
        if cat_id == 'groente_fruit':
            # Hak products are canned/conserved vegetables -> conserven
            if 'hak ' in product_name or product_name.startswith('hak '):
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'
            # Fish salads go to vis
            if 'vissalade' in product_name:
                cat_id, subcat_id = 'vis', 'verse_vis'
            # Olijven are conserved
            if 'olijven' in product_name:
                cat_id, subcat_id = 'conserven_houdbaar', 'conserven'
            # Biscuits/cookies go to snoep
            if 'biscuit' in product_name:
                cat_id, subcat_id = 'snoep_snacks', 'koek'
            # Vlaai/pastries go to bakkerij
            if 'vlaai' in product_name:
                cat_id, subcat_id = 'brood_bakkerij', 'gebak'
            # Broodjes go to bakkerij
            if 'broodje' in product_name:
                cat_id, subcat_id = 'brood_bakkerij', 'brood'
            # Kroketjes could be diepvries if frozen, or snacks
            if 'kroket' in product_name:
                cat_id, subcat_id = 'diepvries', 'kant_klaar'
            # Fruitsap/juice goes to dranken (but not "perssinaasappels" which are oranges for juicing)
            if ('fruitsap' in product_name or 'sap ' in product_name or product_name.endswith('sap')) and 'pers' not in product_name:
                cat_id, subcat_id = 'dranken', 'sap'
            # Jumbo Fruity drinks (250ml, 330ml etc) are juices
            if "jumbo's fruity" in product_name and 'ml' in product_name:
                cat_id, subcat_id = 'dranken', 'sap'

        # Build enriched product
        enriched_product = {
            **product,
            '_bw_category': cat_id,
            '_bw_subcategory': subcat_id,
            '_bw_category_name': CATEGORY_NAMES.get(cat_id, ''),
            '_bw_subcategory_name': SUBCATEGORY_NAMES.get(subcat_id, ''),
        }

        enriched.append(enriched_product)

        # Track statistics
        if cat_id:
            category_stats[cat_id] += 1
        else:
            uncategorized.append({
                'name': product.get('name', 'Unknown'),
                'original_category': original_cat
            })

    return enriched, category_stats, uncategorized


def main():
    print("=" * 60)
    print("BespaarWijzer Product Enrichment v2")
    print("Category-First Approach")
    print("=" * 60)
    print()

    # Load products
    print(f"Loading products: {PRODUCTS_INPUT}")
    with open(PRODUCTS_INPUT, 'r', encoding='utf-8') as f:
        data = json.load(f)

    products = data.get('products', [])
    folder_validity = data.get('folder_validity', {})
    print(f"  Found {len(products)} products")
    print()

    # Enrich products
    print("Enriching products based on original categories...")
    enriched, category_stats, uncategorized = enrich_products(products)

    # Print statistics
    print()
    print("Category distribution:")
    for cat_id in sorted(category_stats.keys()):
        cat_name = CATEGORY_NAMES.get(cat_id, cat_id)
        count = category_stats[cat_id]
        pct = count / len(products) * 100
        print(f"  {cat_name}: {count} ({pct:.1f}%)")

    uncategorized_count = len(uncategorized)
    if uncategorized_count > 0:
        print(f"\n  Uncategorized: {uncategorized_count} ({uncategorized_count/len(products)*100:.1f}%)")
        print("  Sample uncategorized:")
        for item in uncategorized[:10]:
            print(f"    - {item['name'][:40]} | orig: {item['original_category'][:30]}")

    # Save enriched data with same structure as input
    print(f"\nSaving enriched data: {ENRICHED_OUTPUT}")
    ENRICHED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        'products': enriched,
        'folder_validity': folder_validity
    }
    with open(ENRICHED_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False)

    print()
    print("=" * 60)
    print("Enrichment complete!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    main()
