# Lidl Folder Extractor

## Technical Documentation

### Data Source

Lidl uses a JSON API at `/p/api/gridboxes/NL/nl` which returns product data for their online shop and promotions.

**API Endpoint**: `https://www.lidl.nl/p/api/gridboxes/NL/nl`

**Parameters**:
- `category=s10007765` - Main aanbiedingen/offers category
- `pageId=nl_Aanbiedingen` - Alternative approach using page ID

### Data Extracted

The Lidl API is rich with data. Each product includes:

**Basic Info**:
- `id`, `erp_number` - Product identifiers
- `name`, `full_title` - Short and full product names
- `brand` - Brand name, logo URL, and search URL

**Pricing**:
- `price` - Current price
- `base_price_amount`, `base_price_unit`, `base_price_text` - Unit pricing (e.g., "1 m² = 13.18")

**Category**:
- `category` - Full category path (e.g., "Assortiment/Wonen en slapen/Gordijnen & Jaloezieën/Rolgordijnen")
- `category_path` - Numeric path (e.g., "0/31/3160/316014")

**Images**:
- `image_url` - Main product image
- `mouseover_image` - Hover/alternate image
- `image_list` - Array of all product images
- `image_accessibility` - Alt text/description for accessibility

**Product Details**:
- `description` - HTML description with features
- `supplemental_description` - Additional specifications
- `analytics_category` - Analytics categorization

**Ratings**:
- `rating_average` - Average star rating (e.g., 4.6)
- `rating_count` - Number of reviews
- `recommended_yes`, `recommended_no` - Recommendation counts
- `top_rated` - Whether product is top-rated

**Availability**:
- `online_available` - Available for online purchase
- `in_store` - Available in physical stores
- `availability_badges` - Status badges (e.g., "Leverbaar")

**Special Flags**:
- `ribbons` - Special badges like "Tip van Lidl"
- `is_deal_of_day` - Deal of the day indicator
- `is_flash_sale` - Flash sale indicator
- `age_restriction` - Age-restricted product
- `energy_labels` - Energy efficiency labels (for appliances)

**URLs**:
- `product_url` - Direct link to product page
- `source_url` - Canonical URL

### Differences from Dirk/Hoogvliet

| Aspect | Lidl | Dirk | Hoogvliet |
|--------|------|------|-----------|
| Data Source | REST API | NUXT embedded JSON | Publitas folder |
| Product Count | ~25 (non-food focus) | ~130 (full folder) | ~100 (full folder) |
| Has Ratings | ✅ Yes | ❌ No | ❌ No |
| Has Brand Info | ✅ Rich (logo, URL) | Basic | Basic |
| Normal Price | ❌ Not available | ✅ Yes | ✅ Yes |
| Product Type | Online/non-food | Groceries | Groceries |

### Important Notes

1. **Non-food focus**: Lidl's online API primarily returns non-food items (home, clothing, tools). The weekly food promotions may not be available through this API.

2. **No discount info**: Unlike Dirk/Hoogvliet, the Lidl API doesn't provide original/normal prices, so discount percentages cannot be calculated.

3. **Limited pagination**: The API returns up to 25 products per category. Multiple category IDs return the same products.

### Running the Extractor

```bash
cd /Users/yaronkra/Jarvis/tickets/001-supermarket/lidl
python3 extract.py && python3 generate_html.py && open folder.html
```

### Dependencies

```bash
pip install requests
```

### Session Log

#### December 11, 2025
- Created initial extractor using `/p/api/gridboxes` endpoint
- Extracted 25 products with rich data (ratings, brand info, descriptions)
- All 25 products have images
- 23/25 products have customer ratings
- Created HTML viewer with brand filter and rating display
